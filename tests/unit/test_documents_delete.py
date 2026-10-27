"""DELETE /domains/{id}/documents/{id} (feature 012): eliminación completa, alcance, registro y respuestas."""

import json
import uuid

import pytest
from sqlalchemy import func, select

from mia.api.routes import documents as documents_routes
from mia.storage.models import Document, DocumentImage, Domain, Folder
from tests.unit.almacen_falso import AlmacenFalso

COORD = "coord.comp@itcr.ac.cr"
OPERADOR = "operador@itcr.ac.cr"


@pytest.fixture
def almacen(monkeypatch, tmp_path):
    falso = AlmacenFalso()
    subidas = tmp_path / "uploads"
    subidas.mkdir()
    monkeypatch.setattr(documents_routes, "get_vector_store", lambda: falso)
    monkeypatch.setattr(documents_routes, "UPLOAD_DIR", subidas)
    falso.subidas = subidas
    return falso


@pytest.fixture
def mundo(db, units, make_admin, almacen):
    with db() as session:
        session.add_all([Domain(id="d1", unit_id=units.comp, name="Admisión"), Domain(id="d2", unit_id=units.adm, name="Otro")])
        session.flush()
        session.add(Folder(id="f1", domain_id="d1", name="Procesos"))
        session.flush()
        session.add_all([
            Document(id="doc1", domain_id="d1", folder_id="f1", filename="Maestria.txt", source_type="txt", file_hash="h1", status="done"),
            Document(id="doc2", domain_id="d1", filename="requisitos.txt", source_type="txt", file_hash="h2", status="done"),
            Document(id="doc3", domain_id="d2", filename="ajeno.txt", source_type="txt", file_hash="h3", status="done"),
        ])
        session.flush()
        session.add(
            DocumentImage(
                id="img1", document_id="doc1", public_id="p" * 24, content_type="image/png", content=b"png",
                size_bytes=3, position=0, created_by="x",
            )
        )
        session.commit()
    for documento in ("doc1", "doc2", "doc3"):
        almacen.fragmentos[documento] = 3
        (almacen.subidas / f"{documento}.txt").write_text("contenido", encoding="utf-8")
    make_admin(COORD, units=["Computación"])
    make_admin(OPERADOR, global_=True)
    return units


def _ruta(dominio="d1", documento="doc1"):
    return f"/domains/{dominio}/documents/{documento}"


def _lineas(capsys):
    return [json.loads(l) for l in capsys.readouterr().out.splitlines() if l.startswith("{")]


def _existe(db, documento):
    with db() as session:
        return session.get(Document, documento) is not None


def _estado(db, documento):
    with db() as session:
        return session.get(Document, documento).status


def _imagenes(db, documento):
    with db() as session:
        return session.scalar(select(func.count()).select_from(DocumentImage).where(DocumentImage.document_id == documento))


def _inventario(client, headers):
    return client.get("/inventory", headers=headers).json()


def _ids_del_inventario(nodo):
    ids = []
    if isinstance(nodo, dict):
        if "filename" in nodo:
            ids.append(nodo["id"])
        for valor in nodo.values():
            ids += _ids_del_inventario(valor)
    elif isinstance(nodo, list):
        for elemento in nodo:
            ids += _ids_del_inventario(elemento)
    return ids


# --- Eliminar ---------------------------------------------------------------------------------------------------


def test_eliminar_responde_204_y_quita_el_documento_sus_imagenes_fragmentos_y_archivo(client, db, mundo, admin, almacen):
    respuesta = client.delete(_ruta(), headers=admin)

    assert respuesta.status_code == 204 and respuesta.content == b""
    assert not _existe(db, "doc1")
    assert _imagenes(db, "doc1") == 0
    assert almacen.count_chunks("doc1") == 0
    assert not (almacen.subidas / "doc1.txt").exists()
    # Lo demás sigue.
    assert _existe(db, "doc2") and almacen.count_chunks("doc2") == 3


def test_el_enlace_publico_de_la_imagen_deja_de_servir(client, mundo, admin):
    assert client.get("/media/" + "p" * 24).status_code == 200

    client.delete(_ruta(), headers=admin)

    assert client.get("/media/" + "p" * 24).status_code == 404


def test_el_inventario_deja_de_listarlo_y_baja_los_contadores(client, mundo, admin):
    antes = _inventario(client, admin)
    assert "doc1" in _ids_del_inventario(antes)

    client.delete(_ruta(), headers=admin)

    despues = _inventario(client, admin)
    assert "doc1" not in _ids_del_inventario(despues)
    unidad = next(u for u in despues["units"] if u["name"] == "Computación")
    dominio = next(d for d in unidad["domains"] if d["id"] == "d1")
    carpeta = dominio["folders"][0]
    assert carpeta["document_count"] == 0 and dominio["document_count"] == 1 and unidad["document_count"] == 1


# --- 404 --------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ruta",
    [_ruta("d1", "no-existe"), _ruta("no-existe", "doc1"), _ruta("d1", "doc3")],
    ids=["documento inexistente", "dominio inexistente", "documento de otro dominio"],
)
def test_los_documentos_que_no_existen_o_no_son_del_dominio_responden_404(client, db, mundo, admin, almacen, ruta):
    assert client.delete(ruta, headers=admin).status_code == 404
    assert _existe(db, "doc3") and almacen.count_chunks("doc3") == 3


def test_repetir_la_eliminacion_responde_404(client, mundo, admin):
    assert client.delete(_ruta(), headers=admin).status_code == 204
    assert client.delete(_ruta(), headers=admin).status_code == 404


# --- Alcance y registro -----------------------------------------------------------------------------------------


def test_una_cuenta_de_programa_elimina_un_documento_de_su_programa(client, db, mundo, as_user):
    assert client.delete(_ruta(), headers=as_user(COORD)).status_code == 204
    assert not _existe(db, "doc1")


def test_una_cuenta_de_programa_no_elimina_en_otro_programa_y_queda_el_rechazo(client, db, mundo, as_user, almacen, capsys):
    capsys.readouterr()

    respuesta = client.delete(_ruta("d2", "doc3"), headers=as_user(COORD))

    assert respuesta.status_code == 403 and respuesta.json()["code"] == "out_of_scope"
    assert _existe(db, "doc3") and almacen.count_chunks("doc3") == 3 and (almacen.subidas / "doc3.txt").exists()
    lineas = [l for l in _lineas(capsys) if l["actor"] == COORD]
    assert [(l["action"], l["result"]) for l in lineas] == [("document.delete", "rechazado")]


def test_una_cuenta_global_elimina_en_cualquier_dominio_incluso_sin_programa(client, db, mundo, as_user):
    with db() as session:
        session.add(Domain(id="d3", name="Sin programa"))
        session.add(Document(id="doc4", domain_id="d3", filename="x.txt", source_type="txt", file_hash="h4", status="done"))
        session.commit()
    headers = as_user(OPERADOR)

    assert client.delete(_ruta("d2", "doc3"), headers=headers).status_code == 204
    assert client.delete(_ruta("d3", "doc4"), headers=headers).status_code == 204


def test_una_eliminacion_deja_una_linea_con_quien_que_y_de_donde_sin_contenido(client, mundo, as_user, capsys):
    capsys.readouterr()

    client.delete(_ruta(), headers=as_user(OPERADOR))

    lineas = [l for l in _lineas(capsys) if l["actor"] == OPERADOR]
    assert len(lineas) == 1
    linea = lineas[0]
    assert linea["action"] == "document.delete" and linea["result"] == "ok" and linea["ts"]
    assert linea["target"] == "doc1" and linea["detail"] == "Maestria.txt en Admisión"
    assert "contenido" not in json.dumps(linea)


def test_sin_credenciales_o_con_una_clave_de_artefacto_responde_401(client, db, mundo, almacen):
    assert client.delete(_ruta()).status_code == 401
    assert client.delete(_ruta(), headers={"X-Artifact-Key": "mia_x"}).status_code == 401
    assert _existe(db, "doc1") and almacen.count_chunks("doc1") == 3


# --- Fallas del almacén -----------------------------------------------------------------------------------------


def test_si_falla_el_almacen_responde_503_y_el_documento_sigue_y_el_reintento_funciona(client, db, mundo, admin, almacen):
    almacen.falla_al_borrar = True

    respuesta = client.delete(_ruta(), headers=admin)

    assert respuesta.status_code == 503
    assert "sigue como estaba" in respuesta.json()["detail"]
    assert _existe(db, "doc1") and _imagenes(db, "doc1") == 1 and almacen.count_chunks("doc1") == 3
    assert _estado(db, "doc1") == "done"

    almacen.falla_al_borrar = False
    assert client.delete(_ruta(), headers=admin).status_code == 204
    assert not _existe(db, "doc1")


# --- Documentos que se están procesando ---------------------------------------------------------------------------


def test_si_falla_el_almacen_con_el_documento_procesandose_queda_en_error_y_el_reintento_funciona(client, db, mundo, admin, almacen):
    with db() as session:
        session.get(Document, "doc1").status = "processing"
        session.commit()
    almacen.falla_al_borrar = True

    assert client.delete(_ruta(), headers=admin).status_code == 503
    assert _estado(db, "doc1") == "error" and _imagenes(db, "doc1") == 1

    almacen.falla_al_borrar = False
    assert client.delete(_ruta(), headers=admin).status_code == 204
    assert not _existe(db, "doc1")


def test_un_documento_procesandose_cuyo_cerrojo_no_se_libera_responde_409_sin_tocar_nada(
    client, db, mundo, admin, almacen, monkeypatch
):
    from mia.config import settings
    from mia.ingestion import pipeline

    with db() as session:
        session.get(Document, "doc1").status = "processing"
        session.commit()
    monkeypatch.setattr(settings, "delete_wait_seconds", 0.1)

    assert pipeline.acquire_ingest_lock(1)  # la ingesta en curso no suelta el cerrojo
    try:
        respuesta = client.delete(_ruta(), headers=admin)
    finally:
        pipeline.release_ingest_lock()

    assert respuesta.status_code == 409
    assert respuesta.json()["detail"] == "El documento se está procesando; intenta de nuevo en un momento."
    assert _existe(db, "doc1") and _imagenes(db, "doc1") == 1 and almacen.count_chunks("doc1") == 3
    assert not pipeline.is_cancelled("doc1")


# --- Con la clave de automatización (scripts) ---------------------------------------------------------------------


def test_la_clave_de_automatizacion_elimina_y_queda_registrada_como_automatizacion(client, db, mundo, admin, capsys):
    capsys.readouterr()

    respuesta = client.delete(_ruta(), headers=admin)

    assert respuesta.status_code == 204 and not _existe(db, "doc1")
    lineas = [l for l in _lineas(capsys) if l["action"] == "document.delete"]
    assert [(l["actor"], l["target"], l["result"]) for l in lineas] == [("automatizacion", "doc1", "ok")]
    assert client.delete(_ruta(), headers=admin).status_code == 404


def test_un_documento_que_no_es_del_dominio_indicado_responde_404_sin_tocar_nada(client, db, mundo, admin, almacen):
    assert client.delete(_ruta("d2", "doc1"), headers=admin).status_code == 404
    assert _existe(db, "doc1") and almacen.count_chunks("doc1") == 3


# --- Volver a subir el mismo archivo ------------------------------------------------------------------------------


@pytest.fixture
def subida(monkeypatch, almacen):
    from unittest.mock import MagicMock

    from mia.api.routes import domains as domain_routes
    from mia.config import settings

    ingesta = MagicMock()
    monkeypatch.setattr(domain_routes, "ingest_document", ingesta)
    monkeypatch.setattr(domain_routes, "UPLOAD_DIR", almacen.subidas)
    monkeypatch.setattr(settings, "ingestion_enabled", True)
    return ingesta


def _subir(client, headers, dominio="d1", contenido=b"contenido unico del archivo"):
    return client.post(f"/domains/{dominio}/documents", files={"file": ("Maestria.txt", contenido)}, headers=headers)


def test_tras_eliminar_el_mismo_archivo_se_vuelve_a_subir_como_documento_nuevo(client, db, mundo, admin, subida):
    primera = _subir(client, admin)
    assert primera.status_code == 201
    assert _subir(client, admin).json()["already_existed"] is True  # mientras existe, es un duplicado

    assert client.delete(_ruta("d1", primera.json()["id"]), headers=admin).status_code == 204
    segunda = _subir(client, admin)

    assert segunda.status_code == 201
    assert segunda.json()["already_existed"] is False and segunda.json()["id"] != primera.json()["id"]
    assert subida.call_count == 2  # entra de nuevo a la cola de ingesta


def test_el_mismo_contenido_en_otro_dominio_se_acepta_como_antes(client, db, mundo, admin, subida):
    primera = _subir(client, admin, "d1")
    client.delete(_ruta("d1", primera.json()["id"]), headers=admin)

    assert _subir(client, admin, "d2").status_code == 201


def test_el_documento_nuevo_no_hereda_las_imagenes_del_eliminado(client, db, mundo, admin, subida):
    contenido = b"contenido con imagenes"
    original = _subir(client, admin, contenido=contenido).json()["id"]
    with db() as session:
        session.add(
            DocumentImage(
                id=str(uuid.uuid4()), document_id=original, public_id="q" * 24, content_type="image/png",
                content=b"png", size_bytes=3, position=0, created_by="x",
            )
        )
        session.commit()
    client.delete(_ruta("d1", original), headers=admin)

    nuevo = _subir(client, admin, contenido=contenido).json()["id"]

    assert _imagenes(db, nuevo) == 0
    contador = client.get("/inventory", headers=admin).json()
    assert nuevo in _ids_del_inventario(contador)
