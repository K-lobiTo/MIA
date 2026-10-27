"""POST /documents/bulk-delete (feature 012): resultado por documento, fallos parciales y alcance por documento."""

import json

import pytest

from mia.api.routes import documents as documents_routes
from mia.storage.models import Document, Domain
from tests.unit.almacen_falso import AlmacenFalso

COORD = "coord.comp@itcr.ac.cr"
OPERADOR = "operador@itcr.ac.cr"
RUTA = "/documents/bulk-delete"


@pytest.fixture
def almacen(monkeypatch, tmp_path):
    falso = AlmacenFalso()
    subidas = tmp_path / "uploads"
    subidas.mkdir()
    monkeypatch.setattr(documents_routes, "get_vector_store", lambda: falso)
    monkeypatch.setattr(documents_routes, "UPLOAD_DIR", subidas)
    return falso


@pytest.fixture
def mundo(db, units, make_admin, almacen):
    with db() as session:
        session.add_all([Domain(id="d1", unit_id=units.comp, name="Admisión"), Domain(id="d2", unit_id=units.adm, name="Otro")])
        session.flush()
        session.add_all(
            [
                Document(id=f"doc{i}", domain_id="d1" if i < 4 else "d2", filename=f"doc{i}.txt", source_type="txt", file_hash=f"h{i}", status="done")
                for i in range(1, 6)
            ]
        )
        session.commit()
    for i in range(1, 6):
        almacen.fragmentos[f"doc{i}"] = 2
    make_admin(COORD, units=["Computación"])
    make_admin(OPERADOR, global_=True)
    return units


def _post(client, headers, ids):
    return client.post(RUTA, json={"document_ids": ids}, headers=headers)


def _existen(db):
    with db() as session:
        return {d.id for d in session.query(Document).all()}


def _lineas(capsys):
    return [json.loads(l) for l in capsys.readouterr().out.splitlines() if l.startswith("{")]


def test_elimina_varios_y_devuelve_el_resultado_en_el_orden_recibido(client, db, mundo, admin, almacen):
    respuesta = _post(client, admin, ["doc3", "doc1", "doc2"])

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["deleted"] == 3 and cuerpo["failed"] == 0
    assert [(r["document_id"], r["status"], r["filename"]) for r in cuerpo["results"]] == [
        ("doc3", "deleted", "doc3.txt"),
        ("doc1", "deleted", "doc1.txt"),
        ("doc2", "deleted", "doc2.txt"),
    ]
    assert _existen(db) == {"doc4", "doc5"}
    assert almacen.count_chunks("doc1") == 0 and almacen.count_chunks("doc4") == 2


def test_los_ids_repetidos_se_cuentan_una_vez(client, mundo, admin):
    cuerpo = _post(client, admin, ["doc1", "doc1", "doc2", "doc1"]).json()

    assert [r["document_id"] for r in cuerpo["results"]] == ["doc1", "doc2"]
    assert cuerpo["deleted"] == 2


def test_un_id_inexistente_da_not_found_sin_afectar_a_los_demas(client, db, mundo, admin):
    cuerpo = _post(client, admin, ["doc1", "no-existe"]).json()

    assert [(r["document_id"], r["status"]) for r in cuerpo["results"]] == [("doc1", "deleted"), ("no-existe", "not_found")]
    assert "filename" not in cuerpo["results"][1]
    assert cuerpo["deleted"] == 1 and cuerpo["failed"] == 1


def test_cada_documento_se_valida_con_su_propio_alcance(client, db, mundo, as_user, almacen, capsys):
    capsys.readouterr()

    cuerpo = _post(client, as_user(COORD), ["doc1", "doc5", "doc2"]).json()

    estados = {r["document_id"]: r for r in cuerpo["results"]}
    assert estados["doc1"]["status"] == "deleted" and estados["doc2"]["status"] == "deleted"
    assert estados["doc5"]["status"] == "out_of_scope" and "fuera de los programas" in estados["doc5"]["detail"]
    assert "doc5" in _existen(db) and almacen.count_chunks("doc5") == 2
    acciones = [(l["target"] or "-", l["result"]) for l in _lineas(capsys) if l["action"] == "document.delete"]
    assert sorted(acciones) == sorted([("doc1", "ok"), ("doc2", "ok"), ("d2", "rechazado")])


def test_una_cuenta_global_elimina_documentos_de_varios_dominios(client, db, mundo, as_user):
    cuerpo = _post(client, as_user(OPERADOR), ["doc1", "doc5"]).json()

    assert cuerpo["deleted"] == 2 and _existen(db) == {"doc2", "doc3", "doc4"}


def test_un_documento_con_la_falla_del_almacen_da_error_y_sigue_intacto_mientras_los_demas_se_eliminan(client, db, mundo, admin, almacen):
    original = almacen.delete_document

    def falla_en_doc2(document_id):
        if document_id == "doc2":
            raise RuntimeError("Qdrant no responde")
        original(document_id)

    almacen.delete_document = falla_en_doc2

    cuerpo = _post(client, admin, ["doc1", "doc2", "doc3"]).json()

    estados = {r["document_id"]: r["status"] for r in cuerpo["results"]}
    assert estados == {"doc1": "deleted", "doc2": "error", "doc3": "deleted"}
    assert "sigue como estaba" in next(r["detail"] for r in cuerpo["results"] if r["document_id"] == "doc2")
    assert "doc2" in _existen(db) and almacen.count_chunks("doc2") == 2
    assert cuerpo["deleted"] == 2 and cuerpo["failed"] == 1


def test_un_documento_ocupado_da_busy_y_los_demas_se_eliminan(client, db, mundo, admin, monkeypatch):
    def ocupado(session, vector_store, document, upload_dir, wait_seconds):
        if document.id == "doc2":
            raise documents_routes.DocumentBusy(document.id)
        return real(session, vector_store, document, upload_dir, wait_seconds)

    real = documents_routes.remove_document
    monkeypatch.setattr(documents_routes, "remove_document", ocupado)

    cuerpo = _post(client, admin, ["doc1", "doc2"]).json()

    assert {r["document_id"]: r["status"] for r in cuerpo["results"]} == {"doc1": "deleted", "doc2": "busy"}
    assert "doc2" in _existen(db) and "doc1" not in _existen(db)


@pytest.mark.parametrize(
    "cuerpo",
    [
        {"document_ids": []},
        {"document_ids": [f"d{i}" for i in range(101)]},
        {"document_ids": [1, 2]},
        {"document_ids": "doc1"},
        {},
    ],
    ids=["vacía", "más de 100", "no son texto", "no es lista", "sin campo"],
)
def test_un_cuerpo_invalido_responde_422(client, mundo, admin, cuerpo):
    assert client.post(RUTA, json=cuerpo, headers=admin).status_code == 422


def test_con_exactamente_100_ids_se_acepta(client, mundo, admin):
    cuerpo = _post(client, admin, [f"no-existe-{i}" for i in range(100)]).json()

    assert len(cuerpo["results"]) == 100 and cuerpo["deleted"] == 0


def test_sin_credenciales_responde_401(client, db, mundo, almacen):
    assert client.post(RUTA, json={"document_ids": ["doc1"]}).status_code == 401
    assert client.post(RUTA, json={"document_ids": ["doc1"]}, headers={"X-Artifact-Key": "mia_x"}).status_code == 401
    assert "doc1" in _existen(db)


def test_cada_documento_eliminado_deja_su_linea_con_nombre_y_dominio(client, mundo, as_user, capsys):
    capsys.readouterr()

    _post(client, as_user(OPERADOR), ["doc1", "doc5"])

    lineas = [l for l in _lineas(capsys) if l["actor"] == OPERADOR and l["action"] == "document.delete"]
    assert {(l["target"], l["detail"], l["result"]) for l in lineas} == {
        ("doc1", "doc1.txt en Admisión", "ok"),
        ("doc5", "doc5.txt en Otro", "ok"),
    }
