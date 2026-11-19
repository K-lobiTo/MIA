"""Plantillas del artefacto desde el panel (feature 020, US3): CRUD, alcance de administración, auditoría sin contenido y
lectura de archivos."""

import io
import json

import pytest
from docx import Document

from mia.config import settings
from mia.storage.models import ResponseTemplate
from tests.unit.chat_de_prueba import iniciar_sesion
from tests.unit.historial_de_prueba import Pipeline, crear_mundo
from tests.unit.plantillas_de_prueba import CONTENIDO, plantilla_personal, preguntar_con_plantilla

SECRETO = "contenido-secreto-de-la-plantilla"


@pytest.fixture
def artefacto(modes_config, make_artifact, units):
    return make_artifact("Consulta", units=[units.comp], modes="literal,razonamiento,plantilla")


def _crear(client, admin, artefacto, nombre="Informe", contenido=CONTENIDO):
    return client.post(f"/artifacts/{artefacto.id}/templates", json={"name": nombre, "content": contenido}, headers=admin)


def _lineas(capsys):
    return [json.loads(linea) for linea in capsys.readouterr().out.splitlines() if linea.startswith("{")]


def test_lista_con_contenido_y_limites(client, admin, artefacto):
    _crear(client, admin, artefacto, "Informe")

    respuesta = client.get(f"/artifacts/{artefacto.id}/templates", headers=admin)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["limits"] == {
        "max_chars": settings.template_max_chars,
        "max_per_artifact": settings.template_max_per_artifact,
        "file_max_mb": settings.template_file_max_mb,
    }
    (una,) = cuerpo["templates"]
    assert una["name"] == "Informe" and una["content"] == CONTENIDO


def test_crear_guarda_una_del_artefacto_y_la_ven_con_y_sin_sesion_solo_en_ese_artefacto(
    client, admin, db, artefacto, make_artifact, units
):
    otro = make_artifact("Otro", units=[units.comp], modes="literal,razonamiento,plantilla")
    respuesta = _crear(client, admin, artefacto, "Informe de programa")

    assert respuesta.status_code == 201
    with db() as session:
        fila = session.get(ResponseTemplate, respuesta.json()["id"])
        assert fila.scope == "artifact" and fila.owner_key == f"a:{artefacto.id}"
        assert fila.artifact_id == artefacto.id and fila.user_id is None and fila.created_by

    sin_sesion = client.get("/templates", headers=artefacto.headers).json()["artifact"]
    con_sesion = client.get("/templates", headers={**artefacto.headers, **iniciar_sesion(db)["headers"]}).json()["artifact"]
    assert [t["name"] for t in sin_sesion] == [t["name"] for t in con_sesion] == ["Informe de programa"]
    assert client.get("/templates", headers=otro.headers).json()["artifact"] == []


def test_nombre_repetido_es_409_pero_se_permite_el_de_una_personal(client, admin, db, artefacto):
    assert _crear(client, admin, artefacto, "Informe").status_code == 201

    repetido = _crear(client, admin, artefacto, "  informe ")

    assert repetido.status_code == 409
    plantilla_personal(db, iniciar_sesion(db)["uid"], "Informe")  # la misma palabra en una personal es válida
    assert _crear(client, admin, artefacto, "Otro").status_code == 201


def test_validaciones_y_maximo_con_el_limite_en_el_mensaje(client, admin, artefacto, monkeypatch):
    monkeypatch.setattr(settings, "template_max_chars", 200)
    monkeypatch.setattr(settings, "template_max_per_artifact", 2)

    for nombre, contenido, esperado in [
        ("", "x", "vacío"),
        ("a" * 81, "x", "80"),
        ("dos\nlíneas", "x", "saltos de línea"),
        ("Ok", "", "vacío"),
        ("Ok", "x" * 201, "200"),
    ]:
        respuesta = _crear(client, admin, artefacto, nombre, contenido)
        assert respuesta.status_code == 422 and esperado in respuesta.json()["detail"], (nombre, contenido)
    assert _crear(client, admin, artefacto, "Uno").status_code == 201
    assert _crear(client, admin, artefacto, "Dos").status_code == 201
    llena = _crear(client, admin, artefacto, "Tres")
    assert llena.status_code == 422 and "2" in llena.json()["detail"]


def test_editar_sube_la_fecha_y_detecta_la_edicion_concurrente(client, admin, artefacto):
    creada = _crear(client, admin, artefacto, "Informe").json()
    url = f"/artifacts/{artefacto.id}/templates/{creada['id']}"

    editada = client.put(url, json={"name": "Informe 2", "content": "# Nuevo", "expected_updated_at": creada["updated_at"]}, headers=admin)

    assert editada.status_code == 200
    assert editada.json()["name"] == "Informe 2" and editada.json()["content"] == "# Nuevo"
    assert editada.json()["updated_at"] >= creada["updated_at"]
    # Una segunda edición con la fecha vieja: 409 con la versión actual.
    choque = client.put(url, json={"name": "Otra", "content": "x", "expected_updated_at": creada["updated_at"]}, headers=admin)
    assert choque.status_code == 409
    assert choque.json()["current"]["name"] == "Informe 2" and choque.json()["code"] == "template_changed"
    # Sin `expected_updated_at` gana la última edición.
    assert client.put(url, json={"name": "Última", "content": "x"}, headers=admin).status_code == 200


def test_editar_a_un_nombre_ya_usado_es_409(client, admin, artefacto):
    _crear(client, admin, artefacto, "Uno")
    otra = _crear(client, admin, artefacto, "Dos").json()

    respuesta = client.put(f"/artifacts/{artefacto.id}/templates/{otra['id']}", json={"name": "uno", "content": "x"}, headers=admin)

    assert respuesta.status_code == 409


def test_eliminar_y_la_consulta_siguiente_responde_404(client, admin, db, make_artifact, modes_config, monkeypatch):
    mundo = crear_mundo(db, make_artifact, monkeypatch, modes="literal,razonamiento,plantilla")
    creada = _crear(client, admin, mundo).json()
    with Pipeline():
        assert preguntar_con_plantilla(client, mundo, "Prepárame el informe de analítica", creada["id"]).status_code == 200

    assert client.delete(f"/artifacts/{mundo.id}/templates/{creada['id']}", headers=admin).status_code == 204

    with Pipeline():
        respuesta = preguntar_con_plantilla(client, mundo, "Prepárame el informe de analítica", creada["id"])
    assert respuesta.status_code == 404 and respuesta.json()["detail"] == "La plantilla ya no está disponible."


def test_una_plantilla_de_otro_artefacto_o_personal_no_se_toca_desde_este(client, admin, db, artefacto, make_artifact, units):
    otro = make_artifact("Otro", units=[units.comp], modes="literal,razonamiento,plantilla")
    ajena = _crear(client, admin, otro, "Ajena").json()
    personal = plantilla_personal(db, iniciar_sesion(db)["uid"], "Mía")

    for identificador in (ajena["id"], personal, "no-existe"):
        url = f"/artifacts/{artefacto.id}/templates/{identificador}"
        assert client.put(url, json={"name": "x", "content": "y"}, headers=admin).status_code == 404
        assert client.delete(url, headers=admin).status_code == 404


def test_una_cuenta_con_alcance_de_otra_unidad_recibe_404_en_todas_las_rutas(client, db, make_admin, as_user, units, make_artifact, modes_config):
    fuera = make_artifact("De administración", units=[units.adm], modes="literal,razonamiento,plantilla")
    make_admin("coord.comp@itcr.ac.cr", units=["Computación"])
    headers = as_user("coord.comp@itcr.ac.cr")
    base = f"/artifacts/{fuera.id}/templates"

    assert client.get(base, headers=headers).status_code == 404
    assert client.post(base, json={"name": "x", "content": "y"}, headers=headers).status_code == 404
    assert client.put(f"{base}/t", json={"name": "x", "content": "y"}, headers=headers).status_code == 404
    assert client.delete(f"{base}/t", headers=headers).status_code == 404
    assert client.post(f"{base}/extract", files={"file": ("p.txt", b"hola")}, headers=headers).status_code == 404


def test_una_cuenta_con_alcance_sobre_el_artefacto_si_puede(client, make_admin, as_user, artefacto):
    make_admin("coord.comp@itcr.ac.cr", units=["Computación"])
    headers = as_user("coord.comp@itcr.ac.cr")

    assert _crear(client, headers, artefacto, "Informe").status_code == 201


def test_sin_credencial_de_administracion_responde_401_y_la_clave_de_artefacto_no_sirve(client, artefacto):
    base = f"/artifacts/{artefacto.id}/templates"

    assert client.get(base).status_code == 401
    assert client.get(base, headers=artefacto.headers).status_code == 401
    assert client.post(base, json={"name": "x", "content": "y"}, headers=artefacto.headers).status_code == 401


def test_cada_escritura_deja_una_linea_de_auditoria_sin_el_contenido(client, admin, artefacto, capsys):
    creada = _crear(client, admin, artefacto, "Informe", SECRETO).json()
    url = f"/artifacts/{artefacto.id}/templates/{creada['id']}"
    client.put(url, json={"name": "Informe 2", "content": SECRETO + " v2"}, headers=admin)
    client.delete(url, headers=admin)

    salida = capsys.readouterr().out
    lineas = [json.loads(linea) for linea in salida.splitlines() if linea.startswith("{")]
    assert [(l["action"], l["target"]) for l in lineas] == [
        ("template.create", artefacto.id), ("template.update", artefacto.id), ("template.delete", artefacto.id),
    ]
    assert lineas[0]["detail"] == "Consulta: Informe" and lineas[1]["detail"] == "Consulta: Informe 2"
    assert SECRETO not in salida


def _docx_bytes() -> bytes:
    documento = Document()
    documento.add_heading("Informe", level=1)
    documento.add_paragraph("Resumen")
    buffer = io.BytesIO()
    documento.save(buffer)
    return buffer.getvalue()


def test_extraer_aplica_las_mismas_reglas_y_mensajes_que_la_consulta(client, admin, artefacto, monkeypatch):
    base = f"/artifacts/{artefacto.id}/templates/extract"

    ok = client.post(base, files={"file": ("p.docx", _docx_bytes())}, headers=admin)
    assert ok.status_code == 200 and ok.json()["text"].splitlines() == ["Informe", "Resumen"]
    assert client.post(base, files={"file": ("p.txt", b"# Resumen")}, headers=admin).json() == {"text": "# Resumen"}
    pdf = client.post(base, files={"file": ("p.pdf", b"%PDF")}, headers=admin)
    assert pdf.status_code == 422 and pdf.json()["detail"] == "Solo se aceptan archivos .docx o .txt."
    roto = client.post(base, files={"file": ("p.docx", b"no es un zip")}, headers=admin)
    assert roto.status_code == 422 and "dañado o protegido" in roto.json()["detail"]
    assert client.post(base, files={"file": ("p.txt", b"  ")}, headers=admin).json()["detail"] == "El archivo no tiene texto."
    monkeypatch.setattr(settings, "template_max_chars", 200)
    largo = client.post(base, files={"file": ("p.txt", b"x" * 201)}, headers=admin)
    assert largo.status_code == 422 and "200" in largo.json()["detail"]


def test_artifact_out_incluye_la_cantidad_de_plantillas(client, admin, artefacto, make_artifact, units):
    vacio = make_artifact("Vacío", units=[units.comp], modes="literal,razonamiento,plantilla")
    _crear(client, admin, artefacto, "Uno")
    _crear(client, admin, artefacto, "Dos")

    artefactos = {a["id"]: a for a in client.get("/artifacts", headers=admin).json()["artifacts"]}

    assert artefactos[artefacto.id]["template_count"] == 2
    assert artefactos[vacio.id]["template_count"] == 0
