"""API de plantillas de la Consulta (feature 020): lectura (US1), plantillas personales (US2) y lectura de archivos."""

import io

import pytest

from mia.config import settings
from tests.unit.chat_de_prueba import crear_usuario, iniciar_sesion
from tests.unit.historial_de_prueba import Pipeline, crear_mundo
from tests.unit.plantillas_de_prueba import (
    CONTENIDO,
    plantilla_del_artefacto,
    plantilla_personal,
    preguntar_con_plantilla,
)


@pytest.fixture
def artefacto(modes_config, make_artifact):
    return make_artifact("Consulta", modes="literal,razonamiento,plantilla")


def _get(client, artefacto, sesion=None):
    return client.get("/templates", headers={**artefacto.headers, **(sesion["headers"] if sesion else {})})


# --- GET /templates (US1) ---


def test_lista_las_del_artefacto_con_el_modo_habilitado_y_sin_sesion(client, db, artefacto):
    plantilla_del_artefacto(db, artefacto.id, "Informe de programa")

    respuesta = _get(client, artefacto)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["enabled"] is True and cuerpo["can_create"] is False and cuerpo["mine"] == []
    assert cuerpo["limits"] == {
        "max_chars": settings.template_max_chars,
        "max_per_user": settings.template_max_per_user,
        "file_max_mb": settings.template_file_max_mb,
    }
    (una,) = cuerpo["artifact"]
    assert una["name"] == "Informe de programa" and una["content"] == CONTENIDO
    assert set(una) == {"id", "name", "content", "updated_at"} and una["updated_at"].endswith("Z")


def test_con_sesion_trae_las_personales_para_todos_y_las_de_este_artefacto(client, db, artefacto, make_artifact):
    otro = make_artifact("Otro", modes="literal,razonamiento,plantilla")
    ana = iniciar_sesion(db, "ana")
    beto = crear_usuario(db, "beto")
    para_todos = plantilla_personal(db, ana["uid"], "Para todos")
    para_este = plantilla_personal(db, ana["uid"], "Solo este", artifact_id=artefacto.id)
    plantilla_personal(db, ana["uid"], "Solo el otro", artifact_id=otro.id)
    plantilla_personal(db, beto, "De Beto")

    cuerpo = _get(client, artefacto, ana).json()

    assert cuerpo["can_create"] is True
    assert {t["id"]: t["scope"] for t in cuerpo["mine"]} == {para_todos: "all", para_este: "artifact"}
    en_otro = {t["name"] for t in _get(client, otro, ana).json()["mine"]}
    assert en_otro == {"Para todos", "Solo el otro"}


def test_sin_el_modo_habilitado_no_ofrece_nada(client, db, make_artifact, modes_config):
    sin = make_artifact("Sin", modes="literal,razonamiento")
    plantilla_del_artefacto(db, sin.id)
    ana = iniciar_sesion(db, "ana")
    plantilla_personal(db, ana["uid"])

    cuerpo = _get(client, sin, ana).json()

    assert cuerpo["enabled"] is False and cuerpo["artifact"] == [] and cuerpo["mine"] == []


def test_sin_el_razonamiento_configurado_el_modo_no_esta_habilitado(client, db, artefacto, monkeypatch):
    monkeypatch.setattr(settings, "llm_provider_razonamiento", "")
    plantilla_del_artefacto(db, artefacto.id)

    assert _get(client, artefacto).json()["enabled"] is False


def test_sin_clave_de_artefacto_responde_401(client):
    assert client.get("/templates").status_code == 401


# --- Plantillas personales: POST, PUT, DELETE (US2) ---


def _crear(client, artefacto, sesion, nombre="Mi informe", contenido=CONTENIDO, scope="artifact"):
    return client.post(
        "/templates",
        json={"name": nombre, "content": contenido, "scope": scope},
        headers={**artefacto.headers, **sesion["headers"]},
    )


def _con(artefacto, sesion):
    return {**artefacto.headers, **sesion["headers"]}


def test_crear_para_un_artefacto_o_para_todos_y_donde_se_ve_cada_una(client, db, artefacto, make_artifact):
    otro = make_artifact("Otro", modes="literal,razonamiento,plantilla")
    ana = iniciar_sesion(db, "ana")

    solo_este = _crear(client, artefacto, ana, "Solo este", scope="artifact")
    para_todos = _crear(client, artefacto, ana, "Para todos", scope="all")

    assert solo_este.status_code == 201 and para_todos.status_code == 201
    assert solo_este.json()["scope"] == "artifact" and para_todos.json()["scope"] == "all"
    aqui = {t["name"]: t["scope"] for t in _get(client, artefacto, ana).json()["mine"]}
    assert aqui == {"Solo este": "artifact", "Para todos": "all"}
    en_otro = {t["name"]: t["scope"] for t in _get(client, otro, ana).json()["mine"]}
    assert en_otro == {"Para todos": "all"}
    with db() as session:
        from mia.storage.models import ResponseTemplate

        filas = {f.name: f for f in session.query(ResponseTemplate).all()}
        assert filas["Solo este"].artifact_id == artefacto.id and filas["Para todos"].artifact_id is None
        assert filas["Solo este"].owner_key == f"u:{ana['uid']}" and filas["Solo este"].scope == "personal"


def test_otra_persona_nunca_la_ve_ni_puede_cambiarla(client, db, artefacto):
    ana, beto = iniciar_sesion(db, "ana"), iniciar_sesion(db, "beto")
    mia = _crear(client, artefacto, ana).json()

    assert _get(client, artefacto, beto).json()["mine"] == []
    cuerpo = {"name": "x", "content": "y", "scope": "all"}
    assert client.put(f"/templates/{mia['id']}", json=cuerpo, headers=_con(artefacto, beto)).status_code == 404
    assert client.delete(f"/templates/{mia['id']}", headers=_con(artefacto, beto)).status_code == 404
    assert client.delete(f"/templates/{mia['id']}", headers=_con(artefacto, ana)).status_code == 204


def test_sin_sesion_responde_401_y_sin_el_modo_habilitado_403(client, db, artefacto, make_artifact, modes_config):
    sin = make_artifact("Sin", modes="literal,razonamiento")
    ana = iniciar_sesion(db, "ana")

    sin_sesion = client.post("/templates", json={"name": "x", "content": "y", "scope": "all"}, headers=artefacto.headers)
    assert sin_sesion.status_code == 401 and sin_sesion.json()["code"] == "login_required"
    sin_modo = _crear(client, sin, ana)
    assert sin_modo.status_code == 403 and sin_modo.json()["detail"] == "Este artefacto no tiene el modo plantilla."


def test_nombre_repetido_entre_las_personales_es_409_pero_no_con_una_del_artefacto(client, db, artefacto):
    plantilla_del_artefacto(db, artefacto.id, "Informe")
    ana = iniciar_sesion(db, "ana")

    assert _crear(client, artefacto, ana, "Informe", scope="artifact").status_code == 201  # igual a una del artefacto: válido
    repetido = _crear(client, artefacto, ana, "  INFORME ", scope="all")  # entre las suyas, aunque con otro alcance
    assert repetido.status_code == 409 and repetido.json()["detail"] == "Ya tienes una plantilla con ese nombre."


def test_validaciones_y_maximo_con_el_limite_en_el_mensaje(client, db, artefacto, monkeypatch):
    monkeypatch.setattr(settings, "template_max_chars", 200)
    monkeypatch.setattr(settings, "template_max_per_user", 2)
    ana = iniciar_sesion(db, "ana")

    for nombre, contenido, esperado in [
        ("", "x", "vacío"), ("a" * 81, "x", "80"), ("dos\nlíneas", "x", "saltos de línea"),
        ("Ok", " ", "vacío"), ("Ok", "x" * 201, "200"),
    ]:
        respuesta = _crear(client, artefacto, ana, nombre, contenido)
        assert respuesta.status_code == 422 and esperado in respuesta.json()["detail"]
    assert _crear(client, artefacto, ana, "Uno").status_code == 201
    assert _crear(client, artefacto, ana, "Dos").status_code == 201
    llena = _crear(client, artefacto, ana, "Tres")
    assert llena.status_code == 422 and "2" in llena.json()["detail"]
    assert client.post("/templates", json={"name": "x", "content": "y", "scope": "otro"}, headers=_con(artefacto, ana)).status_code == 422


def test_editar_cambia_nombre_contenido_y_alcance_y_rige_en_la_consulta_siguiente(client, db, make_artifact, modes_config, monkeypatch):
    mundo = crear_mundo(db, make_artifact, monkeypatch, modes="literal,razonamiento,plantilla")
    ana = iniciar_sesion(db, "ana")
    creada = _crear(client, mundo, ana, "Informe", "# Viejo", scope="artifact").json()

    editada = client.put(
        f"/templates/{creada['id']}",
        json={"name": "Informe 2", "content": "# Nuevo", "scope": "all", "expected_updated_at": creada["updated_at"]},
        headers=_con(mundo, ana),
    )

    assert editada.status_code == 200
    assert (editada.json()["name"], editada.json()["content"], editada.json()["scope"]) == ("Informe 2", "# Nuevo", "all")
    assert editada.json()["updated_at"] >= creada["updated_at"]
    with Pipeline() as pipeline:
        respuesta = preguntar_con_plantilla(client, mundo, "Prepárame el informe de analítica", creada["id"], headers=ana["headers"])
    assert respuesta.status_code == 200 and "# Nuevo" in pipeline.llm.answer.call_args.args[0]
    assert "# Viejo" not in pipeline.llm.answer.call_args.args[0]
    # Con la fecha vieja: 409 con la versión actual.
    choque = client.put(
        f"/templates/{creada['id']}",
        json={"name": "Otra", "content": "z", "scope": "all", "expected_updated_at": creada["updated_at"]},
        headers=_con(mundo, ana),
    )
    assert choque.status_code == 409 and choque.json()["current"]["name"] == "Informe 2"


def test_eliminar_responde_204_y_una_consulta_posterior_responde_404(client, db, make_artifact, modes_config, monkeypatch):
    mundo = crear_mundo(db, make_artifact, monkeypatch, modes="literal,razonamiento,plantilla")
    ana = iniciar_sesion(db, "ana")
    creada = _crear(client, mundo, ana).json()

    assert client.delete(f"/templates/{creada['id']}", headers=_con(mundo, ana)).status_code == 204

    with Pipeline():
        respuesta = preguntar_con_plantilla(client, mundo, "Prepárame el informe de analítica", creada["id"], headers=ana["headers"])
    assert respuesta.status_code == 404 and respuesta.json()["detail"] == "La plantilla ya no está disponible."
    assert _get(client, mundo, ana).json()["mine"] == []


def test_no_se_toca_una_plantilla_del_artefacto_desde_las_rutas_personales(client, db, artefacto):
    del_artefacto = plantilla_del_artefacto(db, artefacto.id)
    ana = iniciar_sesion(db, "ana")

    assert client.put(f"/templates/{del_artefacto}", json={"name": "x", "content": "y", "scope": "all"}, headers=_con(artefacto, ana)).status_code == 404
    assert client.delete(f"/templates/{del_artefacto}", headers=_con(artefacto, ana)).status_code == 404


def test_eliminar_al_usuario_elimina_sus_plantillas_personales(db, artefacto):
    from sqlalchemy import text

    from mia.storage.models import ConsultaUser, ResponseTemplate

    ana, beto = iniciar_sesion(db, "ana"), iniciar_sesion(db, "beto")
    plantilla_personal(db, ana["uid"], "De ana")
    plantilla_personal(db, beto["uid"], "De beto")
    plantilla_del_artefacto(db, artefacto.id, "Del artefacto")

    with db() as session:
        session.execute(text("PRAGMA foreign_keys=ON"))
        session.delete(session.get(ConsultaUser, ana["uid"]))
        session.commit()
        assert sorted(t.name for t in session.query(ResponseTemplate)) == ["De beto", "Del artefacto"]


def test_las_plantillas_no_quedan_en_los_registros_del_servidor_ni_en_uso(client, db, artefacto, caplog):
    import logging

    from mia.storage.models import QueryLog

    caplog.set_level(logging.DEBUG)
    ana = iniciar_sesion(db, "ana")
    secreto = "contenido-muy-personal-123"

    creada = _crear(client, artefacto, ana, "Privada", secreto).json()
    client.put(f"/templates/{creada['id']}", json={"name": "Privada", "content": secreto + "2", "scope": "all"}, headers=_con(artefacto, ana))
    client.delete(f"/templates/{creada['id']}", headers=_con(artefacto, ana))

    assert secreto not in caplog.text
    with db() as session:
        assert session.query(QueryLog).count() == 0


# --- POST /templates/extract (US2) ---


def _docx() -> bytes:
    from docx import Document

    documento = Document()
    documento.add_heading("Informe de programa", level=1)
    documento.add_paragraph("Resumen")
    buffer = io.BytesIO()
    documento.save(buffer)
    return buffer.getvalue()


def _extraer(client, artefacto, sesion, nombre, contenido):
    return client.post("/templates/extract", files={"file": (nombre, contenido)}, headers=_con(artefacto, sesion))


def test_extraer_de_un_docx_y_de_un_txt(client, db, artefacto):
    ana = iniciar_sesion(db, "ana")

    docx = _extraer(client, artefacto, ana, "p.docx", _docx())
    txt = _extraer(client, artefacto, ana, "p.txt", b"# Resumen\n- Costos")

    assert docx.status_code == 200 and docx.json()["text"].splitlines() == ["Informe de programa", "Resumen"]
    assert txt.status_code == 200 and txt.json() == {"text": "# Resumen\n- Costos"}


def test_extraer_rechaza_el_tipo_el_tamano_y_un_archivo_danado_con_los_mensajes_fijos(client, db, artefacto, monkeypatch):
    ana = iniciar_sesion(db, "ana")

    pdf = _extraer(client, artefacto, ana, "p.pdf", b"%PDF")
    assert pdf.status_code == 422 and pdf.json()["detail"] == "Solo se aceptan archivos .docx o .txt."
    monkeypatch.setattr(settings, "template_file_max_mb", 1)
    grande = _extraer(client, artefacto, ana, "p.txt", b"x" * (1024 * 1024 + 1))
    assert grande.status_code == 413 and grande.json()["detail"] == "El archivo supera el tamaño máximo de 1 MB."
    roto = _extraer(client, artefacto, ana, "p.docx", b"no es un zip")
    assert roto.status_code == 422
    assert roto.json()["detail"] == "No se pudo leer el archivo: está dañado o protegido con contraseña."
    assert _extraer(client, artefacto, ana, "p.txt", b"  \n").json()["detail"] == "El archivo no tiene texto."
    monkeypatch.setattr(settings, "template_max_chars", 200)
    largo = _extraer(client, artefacto, ana, "p.txt", b"x" * 201)
    assert largo.status_code == 422 and largo.json()["detail"] == "El texto del archivo supera el máximo de 200 caracteres."


def test_extraer_no_deja_ningun_archivo_y_exige_sesion(client, db, artefacto, tmp_path, monkeypatch):
    import os
    import tempfile

    temporal = tmp_path / "temporal"
    temporal.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(temporal))
    ana = iniciar_sesion(db, "ana")

    _extraer(client, artefacto, ana, "p.txt", b"hola")
    _extraer(client, artefacto, ana, "p.docx", b"basura")

    assert os.listdir(temporal) == []
    sin_sesion = client.post("/templates/extract", files={"file": ("p.txt", b"hola")}, headers=artefacto.headers)
    assert sin_sesion.status_code == 401
