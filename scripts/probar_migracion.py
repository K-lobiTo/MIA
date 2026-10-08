"""Prueba la migración del panel de administración sobre una COPIA de la base (p. ej. una rama de Neon).

Aplica las migraciones como lo hace la API al arrancar y verifica el resultado: que se conserven los
datos, que quede en la última revisión, que el nombre de un dominio pase a ser único por unidad en vez de
global, y que se pueda ir a la revisión anterior y volver (la ida y vuelta ejercita las restricciones
propias de Postgres, que las pruebas automáticas, hechas sobre SQLite, no cubren).

**Escribe en la base indicada**, así que tiene dos protecciones:
- exige `--es-una-copia`, para que sea una decisión explícita;
- con `--produccion <archivo de variables>` se niega a correr si la base indicada es la misma que la de
  producción (compara servidor y nombre de la base, no la contraseña).

Uso (ver "Checklist de puesta en producción" en docs/OPERACION.md):
    1. En Neon: Branches > Create branch (desde la rama de producción) y copiar la cadena de conexión
       DIRECTA de la rama (sin pooler).
    2. python scripts/probar_migracion.py --url '<cadena de la rama>' --produccion .env.produccion --es-una-copia
    3. Borrar la rama.
"""

import argparse
import sys
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mia.storage.db import BASELINE_REVISION, MIGRATIONS_DIR, _normalize_url, init_db
from mia.storage.models import Domain, Unit

DESTINO = "0002"


@dataclass
class Resultado:
    pasos: list[tuple[str, bool, str]] = field(default_factory=list)

    def registrar(self, nombre: str, ok: bool, detalle: str = "") -> bool:
        self.pasos.append((nombre, ok, detalle))
        print(f"  [{'OK   ' if ok else 'FALLA'}] {nombre}" + (f": {detalle}" if detalle else ""))
        return ok

    @property
    def ok(self) -> bool:
        return all(ok for _, ok, _ in self.pasos)


def misma_base(url_a: str, url_b: str) -> bool:
    """Dos cadenas apuntan a la misma base si coinciden servidor, puerto y nombre (la contraseña no importa)."""
    a, b = make_url(_normalize_url(url_a)), make_url(_normalize_url(url_b))
    return (a.host, a.port, a.database) == (b.host, b.port, b.database)


def _alembic(engine: Engine, accion: str, revision: str) -> None:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    with engine.begin() as conexion:
        config.attributes["connection"] = conexion
        getattr(command, accion)(config, revision)


def _revision(engine: Engine) -> str | None:
    if "alembic_version" not in inspect(engine).get_table_names():
        return None
    with engine.connect() as conexion:
        return conexion.execute(text("SELECT version_num FROM alembic_version")).scalar()


def _conteos(engine: Engine) -> dict[str, int]:
    tablas = set(inspect(engine).get_table_names())
    with engine.connect() as conexion:
        return {t: conexion.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar_one() for t in ("domains", "documents") if t in tablas}


def _unicas_de_dominios(engine: Engine) -> list[tuple[str, list[str]]]:
    return sorted(
        (u["name"] or "(sin nombre)", u["column_names"]) for u in inspect(engine).get_unique_constraints("domains")
    )


def _nombre_unico_por_unidad(engine: Engine, resultado: Resultado) -> None:
    """El mismo nombre de dominio vale en unidades distintas, y se rechaza dentro de la misma unidad.
    Todo dentro de transacciones que se deshacen: la base queda como estaba."""
    ahora = datetime.now(UTC).replace(tzinfo=None)
    sufijo = uuid.uuid4().hex[:8]
    u1, u2 = str(uuid.uuid4()), str(uuid.uuid4())

    def sembrar(session: Session) -> None:
        session.add_all(
            [
                Unit(id=u1, name=f"prueba-1-{sufijo}", description="", created_at=ahora),
                Unit(id=u2, name=f"prueba-2-{sufijo}", description="", created_at=ahora),
            ]
        )
        session.flush()

    with Session(engine) as session:
        try:
            sembrar(session)
            session.add_all(
                [
                    Domain(id=str(uuid.uuid4()), unit_id=u1, name="Currículum", description="", created_at=ahora),
                    Domain(id=str(uuid.uuid4()), unit_id=u2, name="Currículum", description="", created_at=ahora),
                ]
            )
            session.flush()
            resultado.registrar("el mismo nombre de dominio se acepta en dos unidades distintas", True)
        except IntegrityError as error:
            resultado.registrar("el mismo nombre de dominio se acepta en dos unidades distintas", False, str(error.orig)[:120])
        finally:
            session.rollback()

    with Session(engine) as session:
        try:
            sembrar(session)
            session.add(Domain(id=str(uuid.uuid4()), unit_id=u1, name="Currículum", description="", created_at=ahora))
            session.flush()
            session.add(Domain(id=str(uuid.uuid4()), unit_id=u1, name="Currículum", description="", created_at=ahora))
            session.flush()
            resultado.registrar("un nombre repetido dentro de la misma unidad se rechaza", False, "se aceptó")
        except IntegrityError:
            resultado.registrar("un nombre repetido dentro de la misma unidad se rechaza", True)
        finally:
            session.rollback()


def probar(url: str, produccion: str | None = None, ida_y_vuelta: bool = True) -> Resultado:
    """Ejecuta todas las verificaciones sobre `url` y devuelve el resultado (también las imprime)."""
    resultado = Resultado()
    if produccion and misma_base(url, produccion):
        resultado.registrar(
            "la base indicada NO es la de producción", False, "es la misma que la de producción; se aborta sin tocar nada"
        )
        return resultado

    engine = create_engine(_normalize_url(url), pool_pre_ping=True)
    destino = make_url(_normalize_url(url))
    print(f"Base: {destino.drivername} en {destino.host or '(archivo local)'}, base '{destino.database}'")
    if destino.host and "pooler" in destino.host:
        print("  Aviso: es una conexión con pooler. Para migrar conviene la conexión directa de Neon (sin pooler).")
    with engine.connect() as conexion:
        version = conexion.execute(text("select sqlite_version()" if engine.dialect.name == "sqlite" else "select version()")).scalar()
    print(f"  Versión: {version}")

    print("\nAntes de migrar")
    antes_revision, antes_conteos = _revision(engine), _conteos(engine)
    print(f"  Revisión: {antes_revision or '(ninguna: base creada antes de las migraciones)'}")
    print(f"  Filas: {antes_conteos}")
    if "domains" in inspect(engine).get_table_names():
        print(f"  Restricciones únicas de domains: {_unicas_de_dominios(engine)}")
    else:
        print("  La base no tiene tablas: se probará una migración desde cero, no sobre datos existentes.")

    print("\nMigrando (como lo hace la API al arrancar)")
    try:
        init_db(engine)
    except Exception as error:  # noqa: BLE001 (un script de diagnóstico debe mostrar cualquier error de la migración)
        resultado.registrar("la migración termina sin errores", False, f"{type(error).__name__}: {str(error)[:300]}")
        return resultado
    resultado.registrar("la migración termina sin errores", True)
    resultado.registrar("queda en la última revisión", _revision(engine) == DESTINO, f"revisión {_revision(engine)}")
    despues = _conteos(engine)
    resultado.registrar(
        "se conservan todos los datos",
        all(despues.get(t) == n for t, n in antes_conteos.items()),
        f"antes {antes_conteos}, después {despues}",
    )
    tablas = set(inspect(engine).get_table_names())
    nuevas = {"units", "folders", "artifacts", "artifact_units", "artifact_domains", "queries"}
    resultado.registrar("existen las tablas nuevas", nuevas <= tablas, f"faltan {sorted(nuevas - tablas)}" if not nuevas <= tablas else "")
    columnas = {c["name"] for c in inspect(engine).get_columns("domains")}
    resultado.registrar("domains tiene unit_id", "unit_id" in columnas)
    resultado.registrar("documents tiene folder_id", "folder_id" in {c["name"] for c in inspect(engine).get_columns("documents")})
    unicas = _unicas_de_dominios(engine)
    print(f"  Restricciones únicas de domains ahora: {unicas}")
    resultado.registrar(
        "el nombre de dominio ya no es único por sí solo",
        not any(cols == ["name"] for _, cols in unicas),
    )
    resultado.registrar(
        "el nombre de dominio es único por unidad",
        any(cols == ["unit_id", "name"] for _, cols in unicas),
    )
    _nombre_unico_por_unidad(engine, resultado)

    print("\nArrancar otra vez no cambia nada")
    init_db(engine)
    resultado.registrar("una segunda ejecución deja todo igual", _revision(engine) == DESTINO and _conteos(engine) == despues)

    if ida_y_vuelta:
        print(f"\nIda y vuelta: bajar a {BASELINE_REVISION} y volver a {DESTINO}")
        try:
            _alembic(engine, "downgrade", BASELINE_REVISION)
            resultado.registrar(f"se puede volver a la revisión {BASELINE_REVISION}", _revision(engine) == BASELINE_REVISION)
            resultado.registrar(
                "al volver, el nombre de dominio vuelve a ser único",
                any(cols == ["name"] for _, cols in _unicas_de_dominios(engine)),
            )
            _alembic(engine, "upgrade", "head")
            resultado.registrar(f"se puede subir de nuevo a {DESTINO}", _revision(engine) == DESTINO)
            resultado.registrar("los datos siguen intactos tras la ida y vuelta", _conteos(engine) == antes_conteos or _conteos(engine) == despues)
        except Exception as error:  # noqa: BLE001 (idem)
            resultado.registrar("la ida y vuelta termina sin errores", False, f"{type(error).__name__}: {str(error)[:300]}")
    return resultado


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", required=True, help="cadena de conexión de la COPIA de la base (rama de Neon)")
    parser.add_argument("--produccion", help="archivo de variables de producción (p. ej. .env.produccion), para negarse a correr contra ella")
    parser.add_argument("--es-una-copia", action="store_true", help="confirma que --url es una copia desechable")
    parser.add_argument("--sin-ida-y-vuelta", action="store_true", help="no probar bajar a la revisión anterior y volver")
    args = parser.parse_args()

    if not args.es_una_copia:
        print("Esta prueba escribe en la base indicada. Confirma que es una copia desechable con --es-una-copia.")
        return 2
    produccion = None
    if args.produccion:
        from dotenv import dotenv_values

        produccion = dotenv_values(args.produccion).get("DATABASE_URL")
        if not produccion:
            print(f"No encontré DATABASE_URL en {args.produccion}: sin ella no puedo comprobar que la base no sea la de producción.")
            return 2
    else:
        print("Aviso: sin --produccion no se puede comprobar que la base indicada no sea la de producción.\n")

    resultado = probar(args.url, produccion, ida_y_vuelta=not args.sin_ida_y_vuelta)
    print("\n" + ("TODO BIEN: la migración es segura para aplicarla en producción." if resultado.ok else "HAY FALLAS: no hagas el merge hasta resolverlas."))
    return 0 if resultado.ok else 1


if __name__ == "__main__":
    sys.exit(main())
