"""Rechazos de la lectura de una página web (feature 022).

Un solo catálogo con los códigos, el estado HTTP y el mensaje en español de cada rechazo: el lector, la detección, las
direcciones y la ruta lanzan `WebRejection` con `rechazo(código)` y nadie más escribe mensajes. El mensaje es apto para la
persona administradora y nunca lleva contenido de la página. Ver specs/022-ingesta-web-basica/data-model.md."""

from mia.config import settings


class WebRejection(Exception):
    """La página no se puede agregar. `extra` lleva datos de la respuesta (por ejemplo, el documento ya agregado)."""

    def __init__(self, code: str, message: str, status: int, extra: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.extra = extra or {}


# código: (estado HTTP, mensaje). Los `{...}` se llenan con los datos que recibe `rechazo`.
CATALOGO: dict[str, tuple[int, str]] = {
    "invalid_url": (400, "La dirección no es válida: escribe una dirección que empiece con http:// o https://."),
    "private_address": (400, "No se pueden leer direcciones de redes internas."),
    "ingestion_disabled": (
        503,
        (
            "La ingesta de documentos está desactivada en esta instancia. "
            "Ingerir desde una instancia local (ver docs/OPERACION.md)."
        ),
    ),
    "already_added": (
        409,
        "Esa página ya está agregada (leída el {fecha}). Para actualizarla, elimina el documento y vuelve a agregarla.",
    ),
    "login_required": (422, "La página requiere iniciar sesión. Esta versión no puede leerla."),
    "bot_blocked": (
        422,
        "El sitio bloquea la lectura automática (protección anti-bot). No se intenta esquivar.",
    ),
    "forbidden": (
        422,
        "El sitio no permite el acceso a esta página (puede requerir iniciar sesión o bloquear la lectura automática).",
    ),
    "rate_limited": (422, "El sitio pidió esperar antes de volver a leerlo. Intenta más tarde."),
    "robots_disallowed": (
        422,
        "El sitio no permite la lectura automática de esta página (robots.txt).",
    ),
    "not_found": (422, "No se encontró la página (404). Revisa la dirección."),
    "server_error": (422, "El sitio respondió con un error ({codigo})."),
    "unreachable": (422, "No se pudo conectar con el sitio o no respondió a tiempo."),
    "tls_error": (
        422,
        "No se pudo establecer una conexión segura con el sitio (certificado inválido).",
    ),
    "too_many_redirects": (422, "La dirección redirige demasiadas veces."),
    "not_html": (
        422,
        "La dirección no es una página web de texto. Si es un archivo (por ejemplo, un PDF), súbelo como archivo.",
    ),
    "too_large": (422, "La página es demasiado grande para leerla (más de {kb} KB)."),
    "no_content": (
        422,
        (
            "No se pudo extraer contenido suficiente: la página probablemente carga su texto con JavaScript, "
            "que esta versión no ejecuta."
        ),
    ),
    "text_too_large": (413, "El archivo supera el tamaño máximo de {mb} MB."),
}


class _Datos(dict):
    def __missing__(self, clave: str) -> str:
        return "?"


def rechazo(code: str, **datos) -> WebRejection:
    """Arma el `WebRejection` del código con su estado y su mensaje. Los datos que no son del mensaje (por ejemplo,
    `document_id` o `read_at` de `already_added`) viajan en `extra`."""
    estado, plantilla = CATALOGO[code]
    por_defecto = {"kb": settings.web_max_page_kb, "mb": settings.max_upload_mb, "fecha": "una fecha anterior"}
    mensaje = plantilla.format_map(_Datos({**por_defecto, **datos}))
    extra = {clave: valor for clave, valor in datos.items() if clave not in {"kb", "mb", "fecha", "codigo"}}
    return WebRejection(code, mensaje, estado, extra)
