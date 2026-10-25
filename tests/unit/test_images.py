"""Imágenes asociadas a documentos (feature 011): rutas de administración por documento y la ruta pública /media."""

import json
import re

import pytest
from sqlalchemy import event

from mia.config import settings
from mia.storage.models import Document, DocumentImage, Domain
from tests.unit.imagenes_de_prueba import GIF, JPEG, PDF, PNG, png_of_size

COORD = "coord.comp@itcr.ac.cr"
OPERADOR = "operador@itcr.ac.cr"


@pytest.fixture
def mundo(db, units, make_admin):
    with db() as session:
        session.add_all([Domain(id="d1", unit_id=units.comp, name="Admisión"), Domain(id="d2", unit_id=units.adm, name="Otro")])
        session.flush()
        session.add_all([
            Document(id="doc1", domain_id="d1", filename="horario_matricula.pdf", source_type="pdf", file_hash="h1", status="done"),
            Document(id="doc2", domain_id="d1", filename="requisitos.pdf", source_type="pdf", file_hash="h2", status="done"),
            Document(id="doc3", domain_id="d2", filename="ajeno.pdf", source_type="pdf", file_hash="h3", status="done"),
        ])
        session.commit()
    make_admin(COORD, units=["Computación"])
    make_admin(OPERADOR, global_=True)
    return units


def _lineas(capsys):
    return [json.loads(l) for l in capsys.readouterr().out.splitlines() if l.startswith("{")]


def _base(dominio="d1", documento="doc1"):
    return f"/domains/{dominio}/documents/{documento}/images"


def _subir(client, headers, contenido=PNG, nombre="horario.png", caption=None, **ruta):
    data = {"caption": caption} if caption is not None else None
    return client.post(_base(**ruta), files={"file": (nombre, contenido, "image/png")}, data=data, headers=headers)


def _listar(client, headers, **ruta):
    return client.get(_base(**ruta), headers=headers)


def _ids(client, headers, **ruta):
    return [i["id"] for i in _listar(client, headers, **ruta).json()["images"]]


# --- Agregar y listar ------------------------------------------------------------------------------------------


def test_agregar_una_imagen_devuelve_201_con_la_forma_del_contrato(client, mundo, admin):
    respuesta = _subir(client, admin, caption="Horario de matrícula")

    assert respuesta.status_code == 201
    imagen = respuesta.json()
    assert set(imagen) == {"id", "public_id", "url", "content_type", "size_bytes", "caption", "position"}
    assert imagen["url"] == f"/media/{imagen['public_id']}" and len(imagen["public_id"]) >= 20
    assert imagen["content_type"] == "image/png" and imagen["size_bytes"] == len(PNG)
    assert imagen["caption"] == "Horario de matrícula" and imagen["position"] == 0


def test_las_imagenes_nuevas_quedan_al_final_del_orden(client, mundo, admin):
    posiciones = [_subir(client, admin).json()["position"] for _ in range(3)]
    assert posiciones == [0, 1, 2]
    assert [i["position"] for i in _listar(client, admin).json()["images"]] == [0, 1, 2]


def test_las_imagenes_de_otro_documento_llevan_su_propio_orden(client, mundo, admin):
    _subir(client, admin)
    _subir(client, admin)
    assert _subir(client, admin, documento="doc2").json()["position"] == 0


def test_un_jpeg_tambien_se_acepta(client, mundo, admin):
    respuesta = _subir(client, admin, JPEG, "foto.jpg")
    assert respuesta.status_code == 201 and respuesta.json()["content_type"] == "image/jpeg"


def test_sin_descripcion_la_descripcion_queda_vacia(client, mundo, admin):
    assert _subir(client, admin).json()["caption"] == ""


def test_listar_devuelve_las_imagenes_por_posicion_y_el_tamano_maximo(client, mundo, admin, monkeypatch):
    monkeypatch.setattr(settings, "max_image_mb", 3)
    _subir(client, admin, caption="uno")
    _subir(client, admin, JPEG, "b.jpg", caption="dos")

    cuerpo = _listar(client, admin).json()

    assert cuerpo["max_image_mb"] == 3
    assert [i["caption"] for i in cuerpo["images"]] == ["uno", "dos"]
    assert all(set(i) == {"id", "public_id", "url", "content_type", "size_bytes", "caption", "position"} for i in cuerpo["images"])


def test_listar_un_documento_sin_imagenes_da_la_lista_vacia(client, mundo, admin):
    assert _listar(client, admin).json() == {"images": [], "max_image_mb": settings.max_image_mb}


def test_listar_no_lee_el_binario_de_las_imagenes(client, db, mundo, admin):
    for _ in range(3):
        _subir(client, admin)
    sentencias = []
    engine = db.kw["bind"]

    def espiar(conn, cursor, statement, parameters, context, executemany):
        sentencias.append(statement)

    event.listen(engine, "before_cursor_execute", espiar)
    try:
        _listar(client, admin)
    finally:
        event.remove(engine, "before_cursor_execute", espiar)

    consultas = [s for s in sentencias if "document_images" in s]
    assert consultas and all(not re.search(r"document_images\.content(?!_)", s) for s in consultas)


def test_el_documento_debe_pertenecer_al_dominio_de_la_ruta(client, mundo, admin):
    assert _listar(client, admin, dominio="d1", documento="doc3").status_code == 404
    assert _subir(client, admin, dominio="d1", documento="doc3").status_code == 404
    assert _listar(client, admin, dominio="d1", documento="no-existe").status_code == 404
    assert _listar(client, admin, dominio="no-existe", documento="doc1").status_code == 404


# --- Validación ------------------------------------------------------------------------------------------------


def test_una_imagen_que_supera_el_maximo_responde_413_y_no_se_guarda(client, db, mundo, admin, monkeypatch):
    monkeypatch.setattr(settings, "max_image_mb", 1)

    respuesta = _subir(client, admin, png_of_size(1024 * 1024 + 1))

    assert respuesta.status_code == 413
    assert respuesta.json()["detail"] == "La imagen supera el tamaño máximo de 1 MB."
    assert _ids(client, admin) == []


def test_una_imagen_del_tamano_maximo_exacto_se_acepta(client, mundo, admin, monkeypatch):
    monkeypatch.setattr(settings, "max_image_mb", 1)
    assert _subir(client, admin, png_of_size(1024 * 1024)).status_code == 201


@pytest.mark.parametrize("contenido", [GIF, PDF, b"texto", b""])
def test_otro_formato_responde_415_aunque_se_llame_png(client, mundo, admin, contenido):
    respuesta = _subir(client, admin, contenido, "falsa.png")
    assert respuesta.status_code == 415
    assert respuesta.json()["detail"] == "Solo se aceptan imágenes PNG o JPG."
    assert _ids(client, admin) == []


def test_una_imagen_incompleta_o_danada_responde_422(client, mundo, admin):
    assert _subir(client, admin, PNG[:40]).status_code == 422
    respuesta = _subir(client, admin, JPEG[:-2])
    assert respuesta.status_code == 422 and respuesta.json()["detail"] == "La imagen está incompleta o dañada."
    assert _ids(client, admin) == []


def test_una_descripcion_de_mas_de_mil_caracteres_responde_422(client, mundo, admin):
    assert _subir(client, admin, caption="x" * 1001).status_code == 422
    assert _subir(client, admin, caption="x" * 1000).status_code == 201
    assert len(_ids(client, admin)) == 1


def test_el_tipo_declarado_por_el_navegador_no_cuenta(client, mundo, admin):
    # Un PNG real declarado como otra cosa se acepta por su contenido.
    respuesta = client.post(_base(), files={"file": ("x.bin", PNG, "application/octet-stream")}, headers=admin)
    assert respuesta.status_code == 201 and respuesta.json()["content_type"] == "image/png"


def test_sin_archivo_responde_422(client, mundo, admin):
    assert client.post(_base(), data={"caption": "x"}, headers=admin).status_code == 422


# --- Descripción, reemplazo, orden y borrado -------------------------------------------------------------------


def test_cambiar_la_descripcion_y_vaciarla(client, mundo, admin):
    imagen = _subir(client, admin, caption="vieja").json()

    nueva = client.patch(f"{_base()}/{imagen['id']}", json={"caption": "nueva"}, headers=admin)
    assert nueva.status_code == 200 and nueva.json()["caption"] == "nueva"

    vacia = client.patch(f"{_base()}/{imagen['id']}", json={"caption": ""}, headers=admin)
    assert vacia.json()["caption"] == "" and vacia.json()["public_id"] == imagen["public_id"]
    assert client.patch(f"{_base()}/{imagen['id']}", json={"caption": "x" * 1001}, headers=admin).status_code == 422


def test_reemplazar_conserva_descripcion_y_posicion_y_cambia_el_enlace(client, mundo, admin):
    _subir(client, admin, caption="primera")
    imagen = _subir(client, admin, caption="segunda").json()
    anterior = imagen["public_id"]
    assert client.get(f"/media/{anterior}").status_code == 200

    respuesta = client.put(
        f"{_base()}/{imagen['id']}", files={"file": ("nueva.jpg", JPEG, "image/jpeg")}, headers=admin
    )

    assert respuesta.status_code == 200
    nueva = respuesta.json()
    assert nueva["id"] == imagen["id"] and nueva["caption"] == "segunda" and nueva["position"] == 1
    assert nueva["content_type"] == "image/jpeg" and nueva["size_bytes"] == len(JPEG)
    assert nueva["public_id"] != anterior and nueva["url"] == f"/media/{nueva['public_id']}"
    # El enlace anterior deja de servir y el nuevo sirve la imagen nueva.
    assert client.get(f"/media/{anterior}").status_code == 404
    servida = client.get(nueva["url"])
    assert servida.status_code == 200 and servida.content == JPEG and servida.headers["content-type"] == "image/jpeg"


def test_reemplazar_valida_igual_que_agregar(client, mundo, admin, monkeypatch):
    imagen = _subir(client, admin).json()
    ruta = f"{_base()}/{imagen['id']}"

    assert client.put(ruta, files={"file": ("a.png", GIF, "image/png")}, headers=admin).status_code == 415
    assert client.put(ruta, files={"file": ("a.png", PNG[:40], "image/png")}, headers=admin).status_code == 422
    monkeypatch.setattr(settings, "max_image_mb", 1)
    assert client.put(ruta, files={"file": ("a.png", png_of_size(1024 * 1024 + 1), "image/png")}, headers=admin).status_code == 413
    # Nada cambió: el enlace sigue siendo el mismo.
    assert _listar(client, admin).json()["images"][0]["public_id"] == imagen["public_id"]


def test_reordenar_con_exactamente_los_ids_del_documento(client, mundo, admin):
    a, b, c = (_subir(client, admin, caption=n).json()["id"] for n in "abc")

    respuesta = client.put(f"{_base()}/order", json={"image_ids": [c, a, b]}, headers=admin)

    assert respuesta.status_code == 200
    assert [i["id"] for i in respuesta.json()["images"]] == [c, a, b]
    assert [i["position"] for i in respuesta.json()["images"]] == [0, 1, 2]
    assert [i["caption"] for i in _listar(client, admin).json()["images"]] == ["c", "a", "b"]


@pytest.mark.parametrize("variante", ["falta", "sobra", "repetido", "ajeno"])
def test_reordenar_con_una_lista_incorrecta_responde_422_y_no_cambia_nada(client, mundo, admin, variante):
    a, b = (_subir(client, admin, caption=n).json()["id"] for n in "ab")
    otro = _subir(client, admin, documento="doc2").json()["id"]
    listas = {"falta": [a], "sobra": [a, b, "no-existe"], "repetido": [a, a], "ajeno": [a, otro]}

    respuesta = client.put(f"{_base()}/order", json={"image_ids": listas[variante]}, headers=admin)

    assert respuesta.status_code == 422
    assert _ids(client, admin) == [a, b]


def test_quitar_una_imagen_compacta_las_posiciones_y_su_enlace_responde_404(client, mundo, admin):
    a, b, c = (_subir(client, admin).json() for _ in range(3))

    respuesta = client.delete(f"{_base()}/{b['id']}", headers=admin)

    assert respuesta.status_code == 204
    restantes = _listar(client, admin).json()["images"]
    assert [i["id"] for i in restantes] == [a["id"], c["id"]] and [i["position"] for i in restantes] == [0, 1]
    assert client.get(b["url"]).status_code == 404 and client.get(a["url"]).status_code == 200


def test_cambiar_o_borrar_una_imagen_que_no_existe_o_es_de_otro_documento_responde_404(client, mundo, admin):
    ajena = _subir(client, admin, documento="doc2").json()["id"]
    assert client.patch(f"{_base()}/no-existe", json={"caption": "x"}, headers=admin).status_code == 404
    assert client.patch(f"{_base()}/{ajena}", json={"caption": "x"}, headers=admin).status_code == 404
    assert client.delete(f"{_base()}/{ajena}", headers=admin).status_code == 404
    assert client.put(f"{_base()}/{ajena}", files={"file": ("a.png", PNG, "image/png")}, headers=admin).status_code == 404


# --- Alcance y auditoría ---------------------------------------------------------------------------------------


def test_un_administrador_de_programa_gestiona_las_imagenes_de_sus_documentos(client, mundo, as_user):
    headers = as_user(COORD)
    imagen = _subir(client, headers).json()
    assert client.patch(f"{_base()}/{imagen['id']}", json={"caption": "x"}, headers=headers).status_code == 200
    assert client.put(f"{_base()}/order", json={"image_ids": [imagen["id"]]}, headers=headers).status_code == 200
    assert _listar(client, headers).status_code == 200
    assert client.delete(f"{_base()}/{imagen['id']}", headers=headers).status_code == 204


def test_un_administrador_de_programa_no_toca_documentos_de_otro_programa(client, mundo, as_user, admin, capsys):
    ajena = _subir(client, admin, dominio="d2", documento="doc3").json()
    capsys.readouterr()
    headers = as_user(COORD)
    ruta = _base("d2", "doc3")

    respuestas = [
        client.get(ruta, headers=headers),
        client.post(ruta, files={"file": ("a.png", PNG, "image/png")}, headers=headers),
        client.put(f"{ruta}/{ajena['id']}", files={"file": ("a.png", PNG, "image/png")}, headers=headers),
        client.patch(f"{ruta}/{ajena['id']}", json={"caption": "x"}, headers=headers),
        client.put(f"{ruta}/order", json={"image_ids": [ajena["id"]]}, headers=headers),
        client.delete(f"{ruta}/{ajena['id']}", headers=headers),
    ]

    for respuesta in respuestas:
        assert respuesta.status_code == 403 and respuesta.json()["code"] == "out_of_scope"
    assert [l["result"] for l in _lineas(capsys) if l["actor"] == COORD] == ["rechazado"] * 6
    assert _ids(client, admin, dominio="d2", documento="doc3") == [ajena["id"]]


def test_sin_credenciales_responde_401(client, mundo):
    assert client.get(_base()).status_code == 401
    assert client.post(_base(), files={"file": ("a.png", PNG, "image/png")}).status_code == 401
    assert client.delete(f"{_base()}/x").status_code == 401
    # Una clave de artefacto no administra imágenes.
    assert client.get(_base(), headers={"X-Artifact-Key": "mia_x"}).status_code == 401


def test_las_escrituras_dejan_una_linea_con_el_documento_y_sin_el_contenido(client, mundo, as_user, capsys):
    headers = as_user(OPERADOR)
    imagen = _subir(client, headers, caption="secreto de la descripcion").json()
    client.patch(f"{_base()}/{imagen['id']}", json={"caption": "otra"}, headers=headers)
    client.put(f"{_base()}/{imagen['id']}", files={"file": ("a.png", PNG, "image/png")}, headers=headers)
    client.put(f"{_base()}/order", json={"image_ids": [imagen["id"]]}, headers=headers)
    client.delete(f"{_base()}/{imagen['id']}", headers=headers)

    lineas = [l for l in _lineas(capsys) if l["actor"] == OPERADOR]

    assert [l["action"] for l in lineas] == ["image.create", "image.update", "image.replace", "image.reorder", "image.delete"]
    assert all(l["result"] == "ok" and "horario_matricula.pdf" in l["detail"] + l["target"] + l["action"] or l["result"] == "ok" for l in lineas)
    assert lineas[0]["target"] == imagen["id"] and lineas[0]["detail"] == "horario_matricula.pdf"
    texto = json.dumps(lineas)
    assert "secreto de la descripcion" not in texto and "iVBOR" not in texto and imagen["public_id"] not in texto


# --- GET /media/{public_id} ------------------------------------------------------------------------------------


def test_media_es_publica_y_sirve_el_binario_con_sus_encabezados(client, mundo, admin):
    imagen = _subir(client, admin).json()

    respuesta = client.get(imagen["url"])  # sin ningún encabezado de autenticación

    assert respuesta.status_code == 200 and respuesta.content == PNG
    assert respuesta.headers["content-type"] == "image/png"
    assert respuesta.headers["content-length"] == str(len(PNG))
    assert respuesta.headers["cache-control"] == "public, max-age=3600"
    assert respuesta.headers["x-content-type-options"] == "nosniff"


def test_un_jpeg_se_sirve_con_su_tipo(client, mundo, admin):
    imagen = _subir(client, admin, JPEG, "a.jpg").json()
    assert client.get(imagen["url"]).headers["content-type"] == "image/jpeg"


@pytest.mark.parametrize("identificador", ["corto", "a" * 19, "a" * 65, "con espacios" + "a" * 20, "ñ" * 25, "a" * 30 + "$"])
def test_un_identificador_con_forma_invalida_responde_404_sin_consultar_la_base(client, db, mundo, identificador):
    sentencias = []
    engine = db.kw["bind"]

    def espiar(conn, cursor, statement, parameters, context, executemany):
        sentencias.append(statement)

    event.listen(engine, "before_cursor_execute", espiar)
    try:
        respuesta = client.get(f"/media/{identificador}")
    finally:
        event.remove(engine, "before_cursor_execute", espiar)

    assert respuesta.status_code == 404
    assert sentencias == []


def test_un_identificador_inexistente_responde_404(client, mundo):
    assert client.get("/media/" + "a" * 32).status_code == 404


def test_media_no_registra_nada_en_uso(client, db, mundo, admin):
    from mia.storage.models import QueryLog

    imagen = _subir(client, admin).json()
    client.get(imagen["url"])
    with db() as session:
        assert session.query(QueryLog).count() == 0
        assert session.query(DocumentImage).count() == 1
