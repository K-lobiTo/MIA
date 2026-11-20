"""Agregar una página web como fuente por la API (feature 022). Sin red: el lector de páginas se sustituye por un
`FetcherFalso` que devuelve las páginas inventadas de tests/fixtures/web/."""

import hashlib
import json
from unittest.mock import MagicMock

import pytest

from mia.api.routes import documents as documents_routes
from mia.api.routes import domains as domain_routes
from mia.api.routes import web_pages as web_pages_routes
from mia.config import settings
from mia.ingestion import pipeline
from mia.ingestion.web.errors import CATALOGO, rechazo
from mia.storage.models import Document, Domain, Folder, Unit
from tests.unit.almacen_falso import AlmacenFalso
from tests.unit.web_de_prueba import FetcherFalso, pagina, pagina_leida

URL = "https://ejemplo.test/programa"


@pytest.fixture
def mundo(db, tmp_path, monkeypatch):
    with db() as session:
        session.add(Unit(id="u1", name="Computación", description=""))
        session.add(Domain(id="d1", unit_id="u1", name="Currículum", description=""))
        session.add(Domain(id="d2", unit_id="u1", name="Otro", description=""))
        session.flush()
        session.add(Folder(id="f1", domain_id="d1", parent_id=None, name="Posgrados"))
        session.add(Folder(id="f2", domain_id="d2", parent_id=None, name="Ajena"))
        session.commit()
    subidas = tmp_path / "uploads"
    subidas.mkdir()
    almacen = AlmacenFalso()
    embeddings = MagicMock()
    embeddings.embed.side_effect = lambda textos, is_query=False: [[0.1, 0.2, 0.3] for _ in textos]
    for modulo in (domain_routes, documents_routes, web_pages_routes, pipeline):
        monkeypatch.setattr(modulo, "UPLOAD_DIR", subidas)
    monkeypatch.setattr(documents_routes, "get_vector_store", lambda: almacen)
    monkeypatch.setattr(pipeline, "get_vector_store", lambda: almacen)
    monkeypatch.setattr(pipeline, "get_embedding_provider", lambda nombre: embeddings)
    monkeypatch.setattr(pipeline, "SessionLocal", db)
    monkeypatch.setattr(settings, "ingestion_enabled", True)
    monkeypatch.setattr(settings, "ingestion_sync", True)
    almacen.subidas = subidas
    return almacen


@pytest.fixture
def lector(monkeypatch):
    """Lector falso con `programa.html` en la dirección de prueba; las pruebas pueden agregarle más páginas."""
    falso = FetcherFalso({URL: pagina_leida(pagina("programa.html"), url=URL)})
    monkeypatch.setattr(web_pages_routes, "get_page_fetcher", lambda *args, **kwargs: falso)
    return falso


def _agregar(client, admin, cuerpo=None, dominio="d1"):
    return client.post(f"/domains/{dominio}/web-pages", json={"url": URL} if cuerpo is None else cuerpo, headers=admin)


def test_agregar_una_pagina_crea_un_documento_web_listo(client, admin, mundo, lector):
    respuesta = _agregar(client, admin)

    assert respuesta.status_code == 201, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["source_type"] == "web" and cuerpo["status"] == "done"
    assert cuerpo["filename"] == "Maestría de Ejemplo"
    assert cuerpo["source_url"] == URL
    assert cuerpo["status_note"] is None and cuerpo["already_existed"] is False
    assert cuerpo["uploaded_at"]


def test_el_documento_guarda_la_direccion_el_texto_y_el_archivo_puente(client, admin, mundo, lector, db):
    cuerpo = _agregar(client, admin).json()

    with db() as session:
        documento = session.get(Document, cuerpo["id"])
        assert documento.source_url == URL
        assert documento.source_text.splitlines()[0].startswith(f"Fuente: {URL} (consultada el ")
        assert "cuatro semestres" in documento.source_text
        assert documento.file_hash == hashlib.sha256(documento.source_text.encode("utf-8")).hexdigest()
        assert documento.domain_id == "d1" and documento.folder_id is None
    archivo = mundo.subidas / f"{cuerpo['id']}.web"
    assert archivo.read_text(encoding="utf-8") == documento.source_text


def test_el_almacen_recibe_fragmentos_con_el_texto_de_la_pagina(client, admin, mundo, lector):
    cuerpo = _agregar(client, admin).json()

    fragmentos = " ".join(mundo.textos[cuerpo["id"]])
    assert "cuatro semestres" in fragmentos
    assert "Curso: Fundamentos de datos | Créditos: 4" in fragmentos


def test_el_nombre_propio_tiene_prioridad_y_se_recorta(client, admin, mundo, lector):
    assert _agregar(client, admin, {"url": URL, "name": "  Mi nombre  "}).json()["filename"] == "Mi nombre"


def test_un_nombre_en_blanco_usa_el_titulo_y_sin_titulo_el_sitio(client, admin, mundo, lector):
    assert _agregar(client, admin, {"url": URL, "name": "   "}).json()["filename"] == "Maestría de Ejemplo"

    sin_titulo = "<html><body><main><p>" + "Texto de la página sin título. " * 20 + "</p></main></body></html>"
    lector.paginas["https://otro.test/x"] = pagina_leida(sin_titulo, url="https://otro.test/x")
    assert _agregar(client, admin, {"url": "https://otro.test/x"}).json()["filename"] == "otro.test"


def test_un_nombre_de_300_caracteres_se_guarda_recortado_a_200_sin_error(client, admin, mundo, lector):
    respuesta = _agregar(client, admin, {"url": URL, "name": "a" * 300})

    assert respuesta.status_code == 201 and len(respuesta.json()["filename"]) == 200


def test_la_carpeta_del_dominio_se_acepta_y_la_ajena_o_inexistente_no(client, admin, mundo, lector):
    assert _agregar(client, admin, {"url": URL, "folder_id": "f1"}).json()["folder_id"] == "f1"

    assert _agregar(client, admin, {"url": URL, "folder_id": "f2"}).status_code == 422
    assert _agregar(client, admin, {"url": URL, "folder_id": "no-existe"}).status_code == 404


def test_sin_ingesta_sincronica_queda_pendiente_y_se_procesa_en_segundo_plano(client, admin, mundo, lector, monkeypatch):
    monkeypatch.setattr(settings, "ingestion_sync", False)

    respuesta = _agregar(client, admin)

    assert respuesta.status_code == 201 and respuesta.json()["status"] == "pending"
    listado = client.get("/domains/d1/documents", headers=admin).json()
    assert [d["status"] for d in listado] == ["done"]


def test_una_direccion_sin_esquema_se_acepta(client, admin, mundo, lector):
    respuesta = _agregar(client, admin, {"url": "ejemplo.test/programa"})

    assert respuesta.status_code == 201 and respuesta.json()["source_url"] == URL
    assert lector.pedidas == [URL]


def test_la_direccion_final_es_la_que_se_guarda(client, admin, mundo, lector):
    lector.paginas["https://corto.test/p"] = pagina_leida(pagina("programa.html"), url=URL)

    respuesta = _agregar(client, admin, {"url": "https://corto.test/p"})

    assert respuesta.json()["source_url"] == URL


def test_el_inventario_trae_source_url_en_los_documentos_web_y_null_en_los_demas(client, admin, mundo, lector):
    _agregar(client, admin)
    client.post("/domains/d1/documents", files={"file": ("nota.txt", b"Hola mundo desde un archivo")}, headers=admin)

    unidades = client.get("/inventory", headers=admin).json()["units"]
    documentos = {d["filename"]: d for d in _documentos(unidades)}

    assert documentos["Maestría de Ejemplo"]["source_url"] == URL
    assert documentos["Maestría de Ejemplo"]["source_type"] == "web"
    assert documentos["nota.txt"]["source_url"] is None


def _documentos(unidades):
    encontrados = []

    def recorrer(carpetas):
        for carpeta in carpetas:
            encontrados.extend(carpeta["documents"])
            recorrer(carpeta["folders"])

    for unidad in unidades:
        for dominio in unidad["domains"]:
            encontrados.extend(dominio["documents"])
            recorrer(dominio["folders"])
    return encontrados


def test_un_archivo_web_no_se_sube_como_archivo_y_la_subida_normal_trae_source_url_nulo(client, admin, mundo):
    rechazo = client.post("/domains/d1/documents", files={"file": ("pagina.web", b"texto")}, headers=admin)
    assert rechazo.status_code == 400 and "Tipos aceptados: pdf, docx, txt, xlsx, csv." in rechazo.json()["detail"]

    subida = client.post("/domains/d1/documents", files={"file": ("nota.txt", b"Hola")}, headers=admin)
    assert subida.status_code == 201 and subida.json()["source_url"] is None


def test_un_cuerpo_sin_url_o_con_una_direccion_larga_responde_invalid_url_con_detalle_de_texto(client, admin, mundo, lector):
    for cuerpo in ({}, {"url": ""}, {"url": "   "}, {"url": "https://ejemplo.test/" + "a" * 2100}):
        respuesta = _agregar(client, admin, cuerpo)

        assert respuesta.status_code == 400, cuerpo
        assert respuesta.json()["code"] == "invalid_url"
        assert isinstance(respuesta.json()["detail"], str)
    assert lector.pedidas == []


def test_la_consulta_de_la_direccion_se_conserva_en_source_url(client, admin, mundo, lector):
    con_consulta = URL + "?utm_source=correo"
    lector.paginas[con_consulta] = pagina_leida(pagina("programa.html"), url=con_consulta)

    respuesta = _agregar(client, admin, {"url": con_consulta})

    assert respuesta.json()["source_url"] == con_consulta


# ---------- rechazos (US2) ----------

def _lineas(capsys):
    return [json.loads(linea) for linea in capsys.readouterr().out.splitlines() if linea.startswith("{")]


def _inventario_vacio(client, admin, mundo):
    assert client.get("/domains/d1/documents", headers=admin).json() == []
    assert list(mundo.subidas.iterdir()) == []
    assert mundo.textos == {}


CODIGOS_DEL_LECTOR = [
    "login_required", "bot_blocked", "forbidden", "rate_limited", "robots_disallowed", "not_found", "server_error",
    "unreachable", "tls_error", "too_many_redirects", "not_html", "too_large", "no_content", "private_address",
    "invalid_url",
]


@pytest.mark.parametrize("codigo", CODIGOS_DEL_LECTOR)
def test_cada_rechazo_responde_con_su_estado_y_su_codigo_y_no_deja_nada(client, admin, mundo, lector, codigo):
    esperado = rechazo(codigo)
    lector.paginas[URL] = esperado

    respuesta = _agregar(client, admin)

    assert respuesta.status_code == esperado.status
    assert respuesta.json() == {"detail": esperado.message, "code": codigo}
    _inventario_vacio(client, admin, mundo)


def test_el_estado_de_la_pagina_nunca_es_el_de_la_api(client, admin, mundo, lector):
    # Un 401 o un 403 del sitio no pueden volverse un 401 o un 403 de MIA: el panel los toma por un problema de sesión.
    for estado in (401, 403):
        lector.paginas[URL] = pagina_leida("x", estado=estado)
        assert _agregar(client, admin).status_code == 422


def test_cada_rechazo_se_audita_con_la_direccion_sin_consulta_y_sin_contenido(client, admin, mundo, lector, capsys):
    lector.paginas["https://ejemplo.test/a?token=secreto"] = rechazo("login_required")  # sin el fragmento: la ruta lo quita

    _agregar(client, admin, {"url": "https://ejemplo.test/a?token=secreto#x"})

    salida = capsys.readouterr().out
    assert "secreto" not in salida
    lineas = [json.loads(linea) for linea in salida.splitlines() if linea.startswith("{")]
    assert len(lineas) == 1
    assert lineas[0]["action"] == "document.add_web" and lineas[0]["result"] == "rechazado"
    assert lineas[0]["target"] == "d1"
    assert lineas[0]["detail"] == "login_required https://ejemplo.test/a"


def test_una_direccion_con_credenciales_se_registra_sin_la_clave(client, admin, mundo, lector, capsys):
    respuesta = _agregar(client, admin, {"url": "https://usuario:clave-secreta@ejemplo.test/"})

    assert respuesta.status_code == 400 and respuesta.json()["code"] == "invalid_url"
    salida = capsys.readouterr().out
    assert "clave-secreta" not in salida and "usuario" not in salida
    linea = next(json.loads(x) for x in salida.splitlines() if x.startswith("{"))
    assert linea["detail"].startswith("invalid_url ") and linea["result"] == "rechazado"
    assert lector.pedidas == []


def test_una_direccion_que_no_se_puede_interpretar_se_registra_con_el_texto_fijo(client, admin, mundo, lector, capsys):
    _agregar(client, admin, {"url": "javascript:alert('clave-secreta')"})

    salida = capsys.readouterr().out
    assert "clave-secreta" not in salida
    assert "(dirección no interpretable)" in salida


def test_los_rechazos_anteriores_a_la_lectura_se_auditan_y_no_llaman_al_lector(client, admin, mundo, lector, capsys):
    _agregar(client, admin, {"url": "ftp://ejemplo.test/a"})
    _agregar(client, admin, {"url": ""})
    lector.paginas["http://127.0.0.1/"] = rechazo("private_address")

    lineas = _lineas(capsys)

    assert [linea["result"] for linea in lineas] == ["rechazado", "rechazado"]
    assert all(linea["action"] == "document.add_web" for linea in lineas)
    assert lector.pedidas == []


def test_el_intento_aceptado_se_audita_como_ok_con_el_id_del_documento(client, admin, mundo, lector, capsys):
    cuerpo = _agregar(client, admin).json()

    lineas = _lineas(capsys)

    asignado = [linea for linea in lineas if linea["action"] == "document.add_web"]
    assert len(asignado) == 1
    assert asignado[0]["result"] == "ok" and asignado[0]["target"] == cuerpo["id"]
    assert asignado[0]["detail"] == "Maestría de Ejemplo en Currículum"


def test_con_la_ingesta_desactivada_responde_503_sin_leer_nada(client, admin, mundo, lector, monkeypatch, capsys):
    monkeypatch.setattr(settings, "ingestion_enabled", False)

    respuesta = _agregar(client, admin)

    assert respuesta.status_code == 503 and respuesta.json()["code"] == "ingestion_disabled"
    assert respuesta.json()["detail"] == CATALOGO["ingestion_disabled"][1]
    assert lector.pedidas == []
    assert _lineas(capsys)[0]["result"] == "rechazado"


def test_la_deteccion_real_rechaza_lo_que_el_lector_entrega_con_codigo_200(client, admin, mundo, lector):
    casos = {
        "vacia_js.html": "no_content",
        "verificacion_antibot.html": "bot_blocked",
        "ingreso.html": "login_required",
    }
    for archivo, codigo in casos.items():
        lector.paginas[URL] = pagina_leida(pagina(archivo), url=URL)

        respuesta = _agregar(client, admin)

        assert respuesta.status_code == 422 and respuesta.json()["code"] == codigo, archivo
    _inventario_vacio(client, admin, mundo)


def test_la_deteccion_real_rechaza_por_estado_y_por_tipo_de_contenido(client, admin, mundo, lector):
    casos = [
        (pagina_leida("No está", estado=404), "not_found"),
        (pagina_leida("Error", estado=500), "server_error"),
        (pagina_leida("Prohibido", estado=403), "forbidden"),
        (pagina_leida(b"%PDF-1.7", tipo="application/pdf"), "not_html"),
        (pagina_leida("<p>Hola</p>", url="https://ejemplo.test/login"), "login_required"),
    ]
    for leida, codigo in casos:
        lector.paginas[URL] = leida

        respuesta = _agregar(client, admin)

        assert respuesta.status_code == 422 and respuesta.json()["code"] == codigo
    _inventario_vacio(client, admin, mundo)


def test_el_resultado_llega_en_la_misma_peticion(client, admin, mundo, lector):
    lector.paginas[URL] = rechazo("bot_blocked")

    rechazada = _agregar(client, admin)
    lector.paginas[URL] = pagina_leida(pagina("programa.html"), url=URL)
    aceptada = _agregar(client, admin)

    assert rechazada.status_code == 422 and aceptada.status_code == 201


# ---------- una sola página (US3) ----------


def test_el_camino_completo_solo_pide_robots_y_la_pagina_y_nada_ajeno_llega_al_texto(client, admin, mundo, monkeypatch):
    from mia.ingestion.web.fetcher import HttpPageFetcher
    from tests.unit.web_de_prueba import html, resolver_publico, transporte

    enlaces = "https://ejemplo.test/seccion/pagina"
    t = transporte({enlaces: html(pagina("enlaces.html"))})
    lector_real = HttpPageFetcher(resolver=resolver_publico("ejemplo.test"), transporte=t)
    monkeypatch.setattr(web_pages_routes, "get_page_fetcher", lambda *a, **k: lector_real)

    respuesta = _agregar(client, admin, {"url": enlaces})

    assert respuesta.status_code == 201, respuesta.text
    assert t.logicas() == ["https://ejemplo.test/robots.txt", enlaces]
    with_text = " ".join(mundo.textos[respuesta.json()["id"]])
    assert "CONTENIDO-AJENO" not in with_text
    assert "reglamento en PDF (https://ejemplo.test/archivos/reglamento.pdf)" in with_text


def test_una_redireccion_de_la_propia_direccion_se_sigue_pero_el_destino_de_un_enlace_no(client, admin, mundo, monkeypatch):
    from mia.ingestion.web.fetcher import HttpPageFetcher
    from tests.unit.web_de_prueba import Respuesta, html, resolver_publico, transporte

    t = transporte(
        {
            "https://ejemplo.test/corta": Respuesta(301, {"location": "https://ejemplo.test/seccion/pagina"}),
            "https://ejemplo.test/seccion/pagina": html(pagina("enlaces.html")),
        }
    )
    lector_real = HttpPageFetcher(resolver=resolver_publico("ejemplo.test"), transporte=t)
    monkeypatch.setattr(web_pages_routes, "get_page_fetcher", lambda *a, **k: lector_real)

    respuesta = _agregar(client, admin, {"url": "https://ejemplo.test/corta"})

    assert respuesta.status_code == 201 and respuesta.json()["source_url"] == "https://ejemplo.test/seccion/pagina"
    paginas = [u for u in t.logicas() if not u.endswith("/robots.txt")]
    assert paginas == ["https://ejemplo.test/corta", "https://ejemplo.test/seccion/pagina"]


# ---------- reglas de siempre (US5) ----------


def _otra_version(url=URL):
    cambiada = pagina("programa.html").replace("cuatro semestres", "seis semestres")
    return pagina_leida(cambiada, url=url)


def test_la_misma_direccion_con_el_mismo_texto_responde_409_con_el_documento_existente(client, admin, mundo, lector):
    primero = _agregar(client, admin).json()
    lector.pedidas.clear()

    segunda = _agregar(client, admin)

    assert segunda.status_code == 409
    cuerpo = segunda.json()
    assert cuerpo["code"] == "already_added" and cuerpo["document_id"] == primero["id"]
    assert cuerpo["read_at"] and "ya está agregada" in cuerpo["detail"] and "elimina el documento" in cuerpo["detail"]
    assert "de 2026" in cuerpo["detail"]  # la fecha de lectura, en español
    assert len(client.get("/domains/d1/documents", headers=admin).json()) == 1
    assert lector.pedidas == []  # se rechaza antes de leer


def test_la_misma_direccion_con_el_texto_cambiado_tambien_se_rechaza_y_no_hay_reemplazo(client, admin, mundo, lector, db):
    primero = _agregar(client, admin).json()
    lector.paginas[URL] = _otra_version()

    segunda = _agregar(client, admin)

    assert segunda.status_code == 409 and segunda.json()["code"] == "already_added"
    with db() as session:
        assert "cuatro semestres" in session.get(Document, primero["id"]).source_text


def test_la_direccion_final_tras_una_redireccion_tambien_cuenta(client, admin, mundo, lector):
    _agregar(client, admin)
    lector.paginas["https://corto.test/x"] = _otra_version(url=URL)  # la dirección corta termina en la ya agregada

    respuesta = _agregar(client, admin, {"url": "https://corto.test/x"})

    assert respuesta.status_code == 409 and respuesta.json()["code"] == "already_added"
    assert "https://corto.test/x" in lector.pedidas  # esta sí se leyó: solo se supo al ver la dirección final


@pytest.mark.parametrize(
    "variante",
    [URL + "/", "http://ejemplo.test/programa", "https://EJEMPLO.test/programa", URL + "#seccion"],
)
def test_las_variantes_de_la_misma_direccion_se_rechazan_antes_de_leer(client, admin, mundo, lector, variante):
    _agregar(client, admin)
    lector.pedidas.clear()

    respuesta = _agregar(client, admin, {"url": variante})

    assert respuesta.status_code == 409 and lector.pedidas == []


def test_www_y_otra_consulta_no_son_la_misma_direccion_por_direccion(client, admin, mundo, lector):
    _agregar(client, admin)
    www = "https://www.ejemplo.test/programa"
    lector.paginas[www] = _otra_version(url=www)
    consulta = URL + "?pestana=2"
    lector.paginas[consulta] = pagina_leida(pagina("programa.html").replace("cuatro semestres", "tres semestres"), url=consulta)

    assert _agregar(client, admin, {"url": www}).status_code == 201
    assert _agregar(client, admin, {"url": consulta}).status_code == 201


def test_el_duplicado_por_contenido_devuelve_el_documento_existente(client, admin, mundo, lector, db, monkeypatch):
    primero = _agregar(client, admin).json()
    # Mismo contenido de documento: se fija el reloj y la dirección para que el texto guardado coincida byte a byte.
    with db() as session:
        existente = session.get(Document, primero["id"])
        texto, hash_ = existente.source_text, existente.file_hash
    otra = "https://alias.ejemplo.test/programa"
    lector.paginas[otra] = pagina_leida(pagina("programa.html"), url=otra)
    monkeypatch.setattr(
        web_pages_routes,
        "armar_documento",
        lambda url_final, nombre, contenido, ahora: texto,
    )

    respuesta = _agregar(client, admin, {"url": otra})

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["already_existed"] is True and cuerpo["id"] == primero["id"]
    assert hash_ == hashlib.sha256(texto.encode("utf-8")).hexdigest()
    assert len(client.get("/domains/d1/documents", headers=admin).json()) == 1


def test_la_regla_es_por_dominio(client, admin, mundo, lector):
    assert _agregar(client, admin, dominio="d1").status_code == 201
    assert _agregar(client, admin, dominio="d2").status_code == 201


def test_el_texto_que_supera_el_tope_de_documento_se_rechaza_con_413(client, admin, mundo, lector, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_mb", 1)
    grande = "<html><body><main><p>" + "Párrafo largo de relleno para superar el tope. " * 40000 + "</p></main></body></html>"
    lector.paginas[URL] = pagina_leida(grande, url=URL)

    respuesta = _agregar(client, admin)

    assert respuesta.status_code == 413
    assert respuesta.json() == {"detail": "El archivo supera el tamaño máximo de 1 MB.", "code": "text_too_large"}
    _inventario_vacio(client, admin, mundo)


def test_eliminar_un_documento_web_lo_quita_de_todo_y_la_direccion_se_puede_volver_a_agregar(client, admin, mundo, lector):
    primero = _agregar(client, admin).json()
    assert (mundo.subidas / f"{primero['id']}.web").exists()

    borrado = client.delete(f"/domains/d1/documents/{primero['id']}", headers=admin)

    assert borrado.status_code == 204
    assert client.get("/domains/d1/documents", headers=admin).json() == []
    assert not (mundo.subidas / f"{primero['id']}.web").exists()
    assert _agregar(client, admin).status_code == 201


def test_la_eliminacion_multiple_tambien_quita_un_documento_web(client, admin, mundo, lector):
    primero = _agregar(client, admin).json()

    respuesta = client.post("/documents/bulk-delete", json={"document_ids": [primero["id"]]}, headers=admin)

    assert respuesta.status_code == 200 and respuesta.json()["deleted"] == 1
    assert client.get("/domains/d1/documents", headers=admin).json() == []


def test_el_rechazo_por_direccion_repetida_queda_auditado(client, admin, mundo, lector, capsys):
    _agregar(client, admin)
    capsys.readouterr()

    _agregar(client, admin)

    linea = _lineas(capsys)[0]
    assert linea["result"] == "rechazado" and linea["detail"] == f"already_added {URL}"
