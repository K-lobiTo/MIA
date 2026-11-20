"""Reconocer lo que no se puede leer (feature 022, research R5).

Una página puede pedir iniciar sesión, estar detrás de una protección anti-bot, cargar todo su contenido con programación del
navegador o responder con un error. Aquí se decide, por señales (estado, cabeceras, texto característico y formulario de
contraseña), cuál es el caso y se lanza el rechazo con su código, de modo que la persona lo sepa en el momento de agregar la
fuente. **Límite conocido**: una pantalla de bloqueo nueva puede no reconocerse; el respaldo es el mínimo de texto útil
(`WEB_MIN_TEXT_CHARS`) y la revisión del texto una vez agregado. No se intenta esquivar nada (FR-009)."""

import re
from urllib.parse import urlsplit

from mia.config import settings
from mia.ingestion.web.errors import rechazo
from mia.ingestion.web.extract import Extraido
from mia.ingestion.web.fetcher import FetchedPage

# Segmentos de ruta (completos) y sitios que indican que la dirección terminó en una pantalla de ingreso.
SEGMENTOS_DE_INGRESO = {"login", "signin", "sign-in", "sso", "auth", "oauth", "accounts", "adfs", "cas"}
SITIOS_DE_INGRESO = {"login.microsoftonline.com", "accounts.google.com"}
# Marcas (en minúscula) de una pantalla de verificación o de bloqueo.
MARCAS_DE_BLOQUEO = (
    "attention required! | cloudflare",
    "just a moment...",
    "cf-chl",
    "challenge-platform",
    "captcha",
    "g-recaptcha",
    "hcaptcha",
    "access denied",
    "request unsuccessful. incapsula",
    "pardon our interruption",
    "ddos protection by",
)
TIPOS_HTML = {"text/html", "application/xhtml+xml"}
ESTADOS_DE_DESAFIO = {403, 429, 503}
CAMPO_DE_CONTRASENA = re.compile(r"<input\b[^>]*\btype\s*=\s*[\"']?password", re.IGNORECASE)


def _cuerpo(pagina: FetchedPage) -> str:
    return pagina.cuerpo.decode("utf-8", errors="ignore").lower()


def _con_marcas_de_bloqueo(texto: str) -> bool:
    return any(marca in texto for marca in MARCAS_DE_BLOQUEO)


def _es_ingreso(url: str) -> bool:
    partes = urlsplit(url)
    segmentos = {s.lower() for s in partes.path.split("/") if s}
    return (partes.hostname or "").lower() in SITIOS_DE_INGRESO or bool(segmentos & SEGMENTOS_DE_INGRESO)


def _parece_html(cuerpo: bytes) -> bool:
    comienzo = cuerpo[:512].lstrip().lower()
    return comienzo.startswith((b"<!doctype html", b"<html", b"<head", b"<body", b"<?xml"))


def revisar_respuesta(pagina: FetchedPage) -> None:
    """Estado, cabeceras y tipo de contenido, antes de extraer el texto. Lanza `WebRejection` si no sirve."""
    estado = pagina.estado
    cabeceras = pagina.cabeceras
    if estado == 401 or (estado == 403 and "www-authenticate" in cabeceras) or _es_ingreso(pagina.url_final):
        raise rechazo("login_required")
    if estado in ESTADOS_DE_DESAFIO and (
        cabeceras.get("cf-mitigated", "").lower() == "challenge" or _con_marcas_de_bloqueo(_cuerpo(pagina))
    ):
        raise rechazo("bot_blocked")
    if estado == 403:
        raise rechazo("forbidden")
    if estado == 429:
        raise rechazo("rate_limited")
    if estado in (404, 410):
        raise rechazo("not_found")
    if estado >= 300:
        raise rechazo("server_error", codigo=estado)

    tipo = pagina.tipo_contenido.split(";")[0].strip().lower()
    if tipo:
        if tipo not in TIPOS_HTML:
            raise rechazo("not_html")
    elif not _parece_html(pagina.cuerpo):
        raise rechazo("not_html")


def revisar_texto(pagina: FetchedPage, extraido: Extraido) -> None:
    """Después de extraer: el texto útil (sin la primera línea de origen ni el título) debe llegar al mínimo. Si no llega, se
    mira por qué: pantalla de bloqueo con código 200, formulario de ingreso o una página que arma su contenido con
    programación del navegador."""
    if len(extraido.texto) >= settings.web_min_text_chars:
        return
    cuerpo = _cuerpo(pagina)
    if _con_marcas_de_bloqueo(cuerpo):
        raise rechazo("bot_blocked")
    if CAMPO_DE_CONTRASENA.search(pagina.cuerpo.decode("utf-8", errors="ignore")):
        raise rechazo("login_required")
    raise rechazo("no_content")
