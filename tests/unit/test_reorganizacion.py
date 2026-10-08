import importlib.util
import json
from pathlib import Path

import pytest
from sqlalchemy import select

from mia.storage.models import Document, Domain, Folder, Unit

RAIZ_REPO = Path(__file__).resolve().parents[2]


def _cargar_script():
    spec = importlib.util.spec_from_file_location("reorganizar_v2", RAIZ_REPO / "scripts" / "reorganizar_v2.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


script = _cargar_script()


class AlmacenFalso:
    """VectorStore que solo registra los cambios de dominio pedidos."""

    def __init__(self):
        self.cambios: list[tuple[str, str]] = []

    def set_domain(self, document_id: str, domain_id: str) -> None:
        self.cambios.append((document_id, domain_id))


MAPEO = {
    "unidades": [
        {"nombre": "Computación", "descripcion": "Posgrados en Computación"},
        {"nombre": "Administración de Empresas", "descripcion": "Analítica de Negocios"},
    ],
    "dominios": [
        {
            "actual": "Computación: Consejo de Unidad",
            "unidad": "Computación",
            "nombre": "Memoria del Consejo",
            "descripcion": "Actas",
            "origenes": [{"ruta": "CO/Memorias", "carpeta": ["Actas"]}],
        },
        {
            "actual": "Analítica de Negocios: Currículum",
            "unidad": "Administración de Empresas",
            "nombre": "Currículum",
            "descripcion": "Programas",
            "origenes": [
                {"ruta": "AN/PROGRAMAS CURSO", "carpeta": ["Programas de curso"]},
                {"ruta": "AN/REGLAMENTOS", "carpeta": ["Reglamentos"]},
            ],
        },
        {
            "actual": "Computación: Proyectos de graduación",
            "unidad": "Computación",
            "nombre": "Proyectos de graduación: Tesis",
            "descripcion": "Tesis",
            "archivos": ["tesis-1.pdf"],
            "origenes": [{"ruta": "CO/Proyectos", "carpeta": []}],
        },
        {
            "actual": "Computación: Proyectos de graduación",
            "unidad": "Computación",
            "nombre": "Proyectos de graduación: Artículos",
            "descripcion": "Artículos",
            "archivos": ["articulo-1.pdf", "articulo-2.pdf"],
            "origenes": [{"ruta": "CO/Proyectos", "carpeta": []}],
        },
    ],
    "dominios_vacios": [
        {"unidad": "Computación", "nombre": "Docentes", "descripcion": "Profesorado"},
        {"unidad": "Administración de Empresas", "nombre": "Docentes", "descripcion": "Profesorado"},
    ],
}


@pytest.fixture
def raiz(tmp_path):
    archivos = [
        "CO/Memorias/2025/acta-1.pdf",
        "CO/Memorias/2025/acta-2.pdf",
        "AN/PROGRAMAS CURSO/curso-1.docx",
        "AN/REGLAMENTOS/reglamento.docx",
        "CO/Proyectos/tesis-1.pdf",
        "CO/Proyectos/articulo-1.pdf",
        "CO/Proyectos/articulo-2.pdf",
    ]
    for archivo in archivos:
        ruta = tmp_path / archivo
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_bytes(b"x")
    return tmp_path


def _sembrar_dominios_actuales(db) -> None:
    """Los cinco dominios cargados antes de la reorganización (sin unidad ni carpetas)."""
    with db() as session:
        for id_, nombre in [
            ("d-consejo", "Computación: Consejo de Unidad"),
            ("d-curriculum", "Analítica de Negocios: Currículum"),
            ("d-proyectos", "Computación: Proyectos de graduación"),
        ]:
            session.add(Domain(id=id_, name=nombre, description="viejo"))
        session.flush()
        docs = [
            ("doc-a1", "d-consejo", "acta-1.pdf"),
            ("doc-a2", "d-consejo", "acta-2.pdf"),
            ("doc-c1", "d-curriculum", "curso-1.docx"),
            ("doc-c2", "d-curriculum", "reglamento.docx"),
            ("doc-t1", "d-proyectos", "tesis-1.pdf"),
            ("doc-p1", "d-proyectos", "articulo-1.pdf"),
            ("doc-p2", "d-proyectos", "articulo-2.pdf"),
        ]
        for id_, dominio, nombre in docs:
            session.add(
                Document(id=id_, domain_id=dominio, filename=nombre, source_type=nombre.rsplit(".", 1)[1],
                         file_hash=id_, status="done")
            )
        session.commit()


def _estado(db):
    with db() as session:
        unidades = {u.name for u in session.scalars(select(Unit))}
        dominios = {(d.unit.name if d.unit else None, d.name) for d in session.scalars(select(Domain))}
        carpetas = set()
        for carpeta in session.scalars(select(Folder)):
            padre = session.get(Folder, carpeta.parent_id).name if carpeta.parent_id else None
            carpetas.add((carpeta.domain.name, padre, carpeta.name))
        documentos = {
            d.filename: (d.domain.name, d.folder_id and session.get(Folder, d.folder_id).name, d.status)
            for d in session.scalars(select(Document))
        }
    return unidades, dominios, carpetas, documentos


def test_reorganiza_los_dominios_actuales_sin_reprocesar(db, raiz):
    _sembrar_dominios_actuales(db)
    almacen = AlmacenFalso()

    with db() as session:
        script.reorganizar(session, almacen, MAPEO, raiz)

    unidades, dominios, carpetas, documentos = _estado(db)
    assert unidades == {"Computación", "Administración de Empresas"}
    assert dominios == {
        ("Computación", "Memoria del Consejo"),
        ("Administración de Empresas", "Currículum"),
        ("Computación", "Proyectos de graduación: Tesis"),
        ("Computación", "Proyectos de graduación: Artículos"),
        ("Computación", "Docentes"),
        ("Administración de Empresas", "Docentes"),
    }
    assert ("Memoria del Consejo", "Actas", "2025") in carpetas
    assert ("Memoria del Consejo", None, "Actas") in carpetas
    assert documentos["acta-1.pdf"] == ("Memoria del Consejo", "2025", "done")
    assert documentos["curso-1.docx"] == ("Currículum", "Programas de curso", "done")
    assert documentos["reglamento.docx"] == ("Currículum", "Reglamentos", "done")
    assert documentos["tesis-1.pdf"] == ("Proyectos de graduación: Tesis", None, "done")
    assert documentos["articulo-2.pdf"] == ("Proyectos de graduación: Artículos", None, "done")
    # Ningún documento cambió de estado: no se reprocesó nada.
    assert all(estado == "done" for _, _, estado in documentos.values())


def test_solo_los_documentos_que_cambian_de_dominio_tocan_qdrant(db, raiz):
    _sembrar_dominios_actuales(db)
    almacen = AlmacenFalso()

    with db() as session:
        script.reorganizar(session, almacen, MAPEO, raiz)
        ids_destino = {d.name: d.id for d in session.scalars(select(Domain))}

    # Los dominios que solo se renombran conservan su id: sus fragmentos en Qdrant no cambian.
    assert {documento for documento, _ in almacen.cambios} == {"doc-t1", "doc-p1", "doc-p2"}
    assert dict(almacen.cambios)["doc-t1"] == ids_destino["Proyectos de graduación: Tesis"]
    assert dict(almacen.cambios)["doc-p1"] == ids_destino["Proyectos de graduación: Artículos"]
    # El dominio de origen que se repartió en tres ya quedó vacío y se eliminó.
    assert "Computación: Proyectos de graduación" not in ids_destino


def test_una_segunda_corrida_no_cambia_nada(db, raiz):
    _sembrar_dominios_actuales(db)
    with db() as session:
        script.reorganizar(session, AlmacenFalso(), MAPEO, raiz)
    antes = _estado(db)
    almacen = AlmacenFalso()

    with db() as session:
        resultado = script.reorganizar(session, almacen, MAPEO, raiz)

    assert _estado(db) == antes
    assert almacen.cambios == []
    assert resultado.acciones == []


def test_simular_no_escribe_nada(db, raiz):
    _sembrar_dominios_actuales(db)
    antes = _estado(db)
    almacen = AlmacenFalso()

    with db() as session:
        resultado = script.reorganizar(session, almacen, MAPEO, raiz, simular=True)

    assert _estado(db) == antes
    assert almacen.cambios == []
    assert resultado.acciones  # pero sí informa lo que haría


def test_informa_los_documentos_que_no_encuentra_en_el_origen(db, raiz):
    _sembrar_dominios_actuales(db)
    with db() as session:
        session.add(Document(id="doc-x", domain_id="d-consejo", filename="no-esta-en-disco.pdf",
                             source_type="pdf", file_hash="x", status="done"))
        session.commit()

    with db() as session:
        resultado = script.reorganizar(session, AlmacenFalso(), MAPEO, raiz)

    assert resultado.sin_ubicar == ["Memoria del Consejo: no-esta-en-disco.pdf"]


def test_el_mapeo_real_es_coherente_con_el_anexo_a():
    mapeo = json.loads((RAIZ_REPO / "scripts" / "datos" / "reorganizacion_v2.json").read_text())

    assert {u["nombre"] for u in mapeo["unidades"]} == {"Computación", "Administración de Empresas"}
    actuales = {d["actual"] for d in mapeo["dominios"]}
    assert actuales == {
        "Computación: Consejo de Unidad",
        "Computación: Planes de estudio",
        "Computación: Proyectos de graduación",
        "Analítica de Negocios: Consejo de Área",
        "Analítica de Negocios: Currículum",
    }
    proyectos = [d for d in mapeo["dominios"] if d["actual"] == "Computación: Proyectos de graduación"]
    assert {d["nombre"] for d in proyectos} == {
        "Proyectos de graduación: Tesis",
        "Proyectos de graduación: Informes de IPA",
        "Proyectos de graduación: Artículos",
    }
    por_tipo = {d["nombre"].split(": ")[1]: d["archivos"] for d in proyectos}
    assert (len(por_tipo["Tesis"]), len(por_tipo["Informes de IPA"]), len(por_tipo["Artículos"])) == (12, 4, 14)
    todos = [a for lista in por_tipo.values() for a in lista]
    assert len(todos) == len(set(todos)) == 30
    nombres_unidad = {u["nombre"] for u in mapeo["unidades"]}
    assert all(d["unidad"] in nombres_unidad for d in mapeo["dominios"])
    # Con los dominios que se crean vacíos, Computación llega a 7 dominios y Administración de Empresas a 4.
    por_unidad: dict[str, set[str]] = {}
    for d in mapeo["dominios"] + mapeo["dominios_vacios"]:
        por_unidad.setdefault(d["unidad"], set()).add(d["nombre"])
    assert len(por_unidad["Computación"]) == 7
    assert len(por_unidad["Administración de Empresas"]) == 4
