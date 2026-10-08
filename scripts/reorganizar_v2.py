"""Reorganiza los dominios ya cargados en unidades académicas, dominios y carpetas (versión 2).

Es un script de una sola vez: lleva los cinco dominios actuales a la estructura de la sección 2.3 de
docs/Definicion_Requerimientos_V2.md (mapeo en scripts/datos/reorganizacion_v2.json). No vuelve a
procesar ningún documento:

- Renombrar un dominio y asignarle unidad solo toca la base SQL (Qdrant identifica cada dominio por
  su id, que no cambia).
- Los documentos que pasan a otro dominio (los proyectos de graduación de Computación, repartidos en
  tres) cambian además el dominio de sus fragmentos en Qdrant, sin recalcular embeddings.
- Cada documento se ubica en su carpeta según la ruta de su archivo de origen (carpeta tmp/).

Se puede correr más de una vez: la segunda no cambia nada. Con --simular muestra lo que haría sin
escribir nada.

Uso (ver "Reorganización" en docs/OPERACION.md):
    python scripts/reorganizar_v2.py --simular                          # base local del .env
    python scripts/reorganizar_v2.py --env-file .env.produccion --simular
    python scripts/reorganizar_v2.py --env-file .env.produccion         # aplica
"""

import argparse
import json
import os
import sys
import unicodedata
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from mia.storage.models import ArtifactDomain, Document, Domain, Folder, Unit

MAPEO_POR_DEFECTO = Path(__file__).parent / "datos" / "reorganizacion_v2.json"
RAIZ_POR_DEFECTO = Path("tmp")
TIPOS = {".pdf", ".docx", ".txt"}


@dataclass
class Resultado:
    acciones: list[str] = field(default_factory=list)
    sin_ubicar: list[str] = field(default_factory=list)
    resumen: list[str] = field(default_factory=list)


def _nfc(texto: str) -> str:
    # Los nombres de archivo pueden venir descompuestos (tilde aparte) según el sistema de archivos.
    return unicodedata.normalize("NFC", texto)


def _ubicaciones(raiz: Path, origenes: list[dict]) -> dict[str, list[str]]:
    """Nombre de archivo -> carpetas de destino (la carpeta del mapeo más las subcarpetas del origen)."""
    ubicaciones: dict[str, list[str]] = {}
    for origen in origenes:
        base = raiz / origen["ruta"]
        if not base.is_dir():
            raise FileNotFoundError(f"No existe la carpeta de origen: {base}")
        for directorio, _, archivos in os.walk(base):
            subcarpetas = list(Path(directorio).relative_to(base).parts)
            for archivo in archivos:
                if Path(archivo).suffix.lower() in TIPOS:
                    ubicaciones.setdefault(_nfc(archivo), list(origen.get("carpeta", [])) + subcarpetas)
    return ubicaciones


def _obtener_unidad(session: Session, datos: dict, resultado: Resultado) -> Unit:
    unidad = session.scalar(select(Unit).where(Unit.name == datos["nombre"]))
    if unidad is None:
        unidad = Unit(id=str(uuid.uuid4()), name=datos["nombre"], description=datos.get("descripcion", ""))
        session.add(unidad)
        session.flush()
        resultado.acciones.append(f"Crear unidad '{unidad.name}'")
    return unidad


def _obtener_dominio_vacio(session: Session, unidad: Unit, datos: dict, resultado: Resultado) -> None:
    existente = session.scalar(select(Domain).where(Domain.unit_id == unidad.id, Domain.name == datos["nombre"]))
    if existente is None:
        session.add(
            Domain(id=str(uuid.uuid4()), unit_id=unidad.id, name=datos["nombre"], description=datos.get("descripcion", ""))
        )
        session.flush()
        resultado.acciones.append(f"Crear dominio vacío '{datos['nombre']}' en '{unidad.name}'")


def _carpeta(session: Session, dominio: Domain, ruta: list[str], resultado: Resultado) -> Folder | None:
    """Carpeta al final de la ruta (la crea con sus padres si falta); None si la ruta está vacía."""
    padre: Folder | None = None
    for posicion, nombre in enumerate(ruta):
        carpeta = session.scalar(
            select(Folder).where(
                Folder.domain_id == dominio.id,
                Folder.parent_id == (padre.id if padre else None),
                Folder.name == nombre,
            )
        )
        if carpeta is None:
            carpeta = Folder(id=str(uuid.uuid4()), domain_id=dominio.id, parent_id=padre.id if padre else None, name=nombre)
            session.add(carpeta)
            session.flush()
            resultado.acciones.append(f"Crear carpeta '{'/'.join(ruta[: posicion + 1])}' en '{dominio.name}'")
        padre = carpeta
    return padre


def reorganizar(session: Session, almacen, mapeo: dict, raiz: Path, simular: bool = False) -> Resultado:
    """Aplica el mapeo. `almacen` solo necesita `set_domain(document_id, domain_id)`.

    Con `simular` no escribe nada: ni en la base (se deshace al final) ni en Qdrant. El que llama
    decide cuándo confirmar: aquí se hace `commit` solo si no se simula.
    """
    resultado = Resultado()
    unidades = {u["nombre"]: _obtener_unidad(session, u, resultado) for u in mapeo["unidades"]}
    usos: dict[str, int] = {}
    for entrada in mapeo["dominios"]:
        usos[entrada["actual"]] = usos.get(entrada["actual"], 0) + 1

    origenes_a_borrar: set[str] = set()
    for entrada in mapeo["dominios"]:
        unidad = unidades[entrada["unidad"]]
        destino = session.scalar(select(Domain).where(Domain.unit_id == unidad.id, Domain.name == entrada["nombre"]))
        origen = session.scalar(select(Domain).where(Domain.name == entrada["actual"]))
        if destino is None:
            if origen is not None and usos[entrada["actual"]] == 1:
                # Un solo destino: el dominio actual se renombra en su lugar y conserva su id.
                destino = origen
                destino.unit_id = unidad.id
                destino.name = entrada["nombre"]
                destino.description = entrada["descripcion"]
                resultado.acciones.append(f"Renombrar '{entrada['actual']}' a '{entrada['nombre']}' en '{unidad.name}'")
            else:
                destino = Domain(
                    id=str(uuid.uuid4()), unit_id=unidad.id, name=entrada["nombre"], description=entrada["descripcion"]
                )
                session.add(destino)
                resultado.acciones.append(f"Crear dominio '{entrada['nombre']}' en '{unidad.name}'")
            session.flush()
        if origen is not None and origen.id != destino.id:
            origenes_a_borrar.add(origen.id)

        ubicaciones = _ubicaciones(raiz, entrada["origenes"])
        archivos = {_nfc(a) for a in entrada["archivos"]} if "archivos" in entrada else None

        if origen is not None and origen.id != destino.id:
            candidatos = session.scalars(select(Document).where(Document.domain_id == origen.id)).all()
            for documento in candidatos:
                if archivos is not None and _nfc(documento.filename) not in archivos:
                    continue
                documento.domain_id = destino.id
                documento.folder_id = None
                if not simular:
                    almacen.set_domain(documento.id, destino.id)
                resultado.acciones.append(f"Mover '{documento.filename}' a '{destino.name}' (y sus fragmentos en Qdrant)")
            session.flush()

        for documento in session.scalars(select(Document).where(Document.domain_id == destino.id)).all():
            ruta = ubicaciones.get(_nfc(documento.filename))
            if ruta is None:
                resultado.sin_ubicar.append(f"{destino.name}: {documento.filename}")
                continue
            carpeta = _carpeta(session, destino, ruta, resultado)
            nuevo = carpeta.id if carpeta else None
            if documento.folder_id != nuevo:
                documento.folder_id = nuevo
                resultado.acciones.append(f"Ubicar '{documento.filename}' en '{'/'.join(ruta) or 'raíz'}' de '{destino.name}'")
        session.flush()

    # Un dominio de origen repartido entre varios destinos ya quedó vacío: se elimina.
    for dominio_id in origenes_a_borrar:
        quedan = session.scalar(select(Document.id).where(Document.domain_id == dominio_id).limit(1))
        referenciado = session.scalar(select(ArtifactDomain.artifact_id).where(ArtifactDomain.domain_id == dominio_id).limit(1))
        dominio = session.get(Domain, dominio_id)
        if quedan is None and referenciado is None and dominio is not None:
            session.delete(dominio)
            resultado.acciones.append(f"Eliminar el dominio vacío '{dominio.name}'")
    session.flush()

    for vacio in mapeo.get("dominios_vacios", []):
        _obtener_dominio_vacio(session, unidades[vacio["unidad"]], vacio, resultado)

    resultado.resumen = _resumen(session)
    if simular:
        session.rollback()
    else:
        session.commit()
    return resultado


def _resumen(session: Session) -> list[str]:
    lineas = []
    unidades = session.scalars(select(Unit).order_by(Unit.name)).all()
    for unidad in unidades:
        dominios = session.scalars(select(Domain).where(Domain.unit_id == unidad.id).order_by(Domain.name)).all()
        total = sum(_contar(session, d.id) for d in dominios)
        lineas.append(f"{unidad.name} ({len(dominios)} dominios, {total} documentos)")
        for dominio in dominios:
            lineas.append(f"  {dominio.name} ({_contar(session, dominio.id)} documentos)")
            raiz = session.scalars(
                select(Folder).where(Folder.domain_id == dominio.id, Folder.parent_id.is_(None)).order_by(Folder.name)
            ).all()
            for carpeta in raiz:
                lineas.extend(_resumen_carpeta(session, carpeta, 2))
    sueltos = session.scalars(select(Domain).where(Domain.unit_id.is_(None)).order_by(Domain.name)).all()
    for dominio in sueltos:
        lineas.append(f"SIN UNIDAD: {dominio.name} ({_contar(session, dominio.id)} documentos)")
    return lineas


def _resumen_carpeta(session: Session, carpeta: Folder, nivel: int) -> list[str]:
    ids = _ids_de_carpeta(session, carpeta)
    cantidad = len(session.scalars(select(Document.id).where(Document.folder_id.in_(ids))).all())
    lineas = [f"{'  ' * nivel}{carpeta.name}/ ({cantidad} documentos)"]
    hijas = session.scalars(select(Folder).where(Folder.parent_id == carpeta.id).order_by(Folder.name)).all()
    for hija in hijas:
        lineas.extend(_resumen_carpeta(session, hija, nivel + 1))
    return lineas


def _ids_de_carpeta(session: Session, carpeta: Folder) -> list[str]:
    ids = [carpeta.id]
    for hija in session.scalars(select(Folder).where(Folder.parent_id == carpeta.id)).all():
        ids.extend(_ids_de_carpeta(session, hija))
    return ids


def _contar(session: Session, dominio_id: str) -> int:
    return len(session.scalars(select(Document.id).where(Document.domain_id == dominio_id)).all())


def _cargar_entorno(ruta: str) -> None:
    """Carga un archivo de variables (p. ej. .env.produccion) antes de importar la configuración."""
    from dotenv import dotenv_values

    for clave, valor in dotenv_values(ruta).items():
        if valor is not None:
            os.environ[clave] = valor


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mapeo", type=Path, default=MAPEO_POR_DEFECTO, help="archivo JSON con el mapeo")
    parser.add_argument("--raiz", type=Path, default=RAIZ_POR_DEFECTO, help="carpeta que contiene los orígenes (tmp/)")
    parser.add_argument("--env-file", help="archivo de variables (p. ej. .env.produccion) con DATABASE_URL y Qdrant")
    parser.add_argument("--simular", action="store_true", help="muestra lo que haría sin escribir nada")
    args = parser.parse_args()

    if args.env_file:
        _cargar_entorno(args.env_file)
    mapeo = json.loads(args.mapeo.read_text(encoding="utf-8"))

    # La configuración se lee al importar, por eso estos imports van después de cargar el entorno.
    from sqlalchemy import inspect

    from mia.config import settings
    from mia.storage.db import SessionLocal, engine, init_db
    from mia.storage.vector_store import get_vector_store

    destino_base = engine.url.render_as_string(hide_password=True)
    print(f"Base de datos: {destino_base}")
    print(f"Qdrant: {settings.qdrant_url} (colección {settings.qdrant_collection})")
    if args.simular:
        # Simular no debe modificar la base: si el esquema no está migrado, se avisa y se sale.
        columnas = {c["name"] for c in inspect(engine).get_columns("domains")} if inspect(engine).has_table("domains") else set()
        if "unit_id" not in columnas:
            print("El esquema aún no tiene las unidades. Arranca la API (aplica las migraciones) o corre sin --simular.")
            return 1
    else:
        init_db()

    try:
        with SessionLocal() as session:
            resultado = reorganizar(session, get_vector_store(), mapeo, args.raiz, simular=args.simular)
    except FileNotFoundError as error:
        print(error)
        return 1

    titulo = "SIMULACIÓN, no se escribió nada" if args.simular else "APLICADO"
    print(f"\n== {titulo}: {len(resultado.acciones)} cambios ==")
    for accion in resultado.acciones:
        print(f"  - {accion}")
    if resultado.sin_ubicar:
        print(f"\nDocumentos que no se encontraron en las carpetas de origen ({len(resultado.sin_ubicar)}):")
        for linea in resultado.sin_ubicar:
            print(f"  ! {linea}")
    print("\n== Estructura resultante ==")
    for linea in resultado.resumen:
        print(linea)
    return 0


if __name__ == "__main__":
    sys.exit(main())
