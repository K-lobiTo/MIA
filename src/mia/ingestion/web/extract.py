"""Del HTML de una página al texto de un documento (feature 022).

Extractor propio sobre `lxml` (research R1): toma el contenido principal, descarta menús, pie de página, botones y avisos
de cookies, y lo escribe como texto regular, una idea por línea: títulos en su línea, viñetas con guion, las tablas con el
mismo formato de fila que el Excel (`Encabezado: valor | Encabezado: valor`) y cada enlace como `texto (dirección)`. Nunca
devuelve direcciones para visitar: las páginas enlazadas no se leen (FR-002)."""

import codecs
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urljoin, urlsplit
from zoneinfo import ZoneInfo

from lxml import etree
from lxml import html as lhtml

from mia.config import settings
from mia.ingestion.loaders.tabular import lineas_de_tabla

MESES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre",
    "diciembre",
)
NOMBRE_MAX = 200

# Elementos que nunca aportan texto de contenido, estén donde estén.
SIEMPRE_FUERA = {
    "script", "style", "noscript", "template", "iframe", "svg", "canvas", "object", "embed", "video", "audio",
    "picture", "img", "map", "select", "option", "datalist", "dialog", "link", "meta", "head",
}
# Además se descartan dentro del contenido principal. `header` solo se descarta si no se encontró `main`, `article` ni
# `[role=main]` (dentro de un artículo suele traer el título).
FUERA_EN_CONTENIDO = {"nav", "aside", "form", "button", "footer"}
FUERA_SIN_CONTENIDO_PRINCIPAL = FUERA_EN_CONTENIDO | {"header"}
# Contenedores que se descartan por su `class` o su `id`: solo cuando una **clase completa** (o el id completo) es una de
# estas palabras. `menu-item-description` o `share-price-table` no coinciden y se conservan (así no se pierde contenido que
# solo parece ruido por su nombre).
CLASES_DE_RUIDO = {
    "menu", "nav", "navbar", "navigation", "cookie", "cookies", "cookie-banner", "cookie-notice", "cookie-consent",
    "banner", "breadcrumb", "breadcrumbs", "social", "social-share", "share", "sharing", "footer", "sidebar", "ads",
    "ad", "advert", "advertisement", "popup", "modal", "newsletter", "skip-link",
}
BLOQUES = {
    "p", "div", "section", "article", "main", "header", "footer", "aside", "nav", "blockquote", "pre", "dl", "dt", "dd",
    "figure", "figcaption", "address", "details", "summary", "fieldset", "hr", "form", "h1", "h2", "h3", "h4", "h5", "h6",
    "tr", "thead", "tbody", "tfoot", "caption", "center", "body", "html",
}
ENCABEZADOS = {"h1", "h2", "h3", "h4", "h5", "h6"}
SOLO_VINETA = re.compile(r"^[-•*·–]+$")
CONTROL = re.compile("[\x00-\x08\x0b-\x1f\x7f-\x9f\u200b-\u200d\u2060\ufeff]")
# Separadores de un título como "Programa | Sitio" (los guiones medio y largo van como escapes: el proyecto no escribe el largo).
SEPARADORES_DE_TITULO = (" | ", " - ", " \u2013 ", " \u00b7 ", " \u2014 ")


@dataclass
class Extraido:
    titulo: str
    texto: str


# ---------- texto ----------


def _normalizar(texto: str) -> str:
    """Una línea: NFC, sin caracteres de control ni espacios especiales, con los espacios repetidos unidos."""
    texto = unicodedata.normalize("NFC", texto)
    texto = CONTROL.sub("", texto)
    texto = "".join(" " if unicodedata.category(c) == "Zs" else c for c in texto)
    return " ".join(texto.split())


def _lineas_de(texto: str) -> list[str]:
    return [linea for linea in (_normalizar(parte) for parte in texto.split("\n")) if linea]


# ---------- decodificación ----------


def _declarada(contenido: bytes) -> str | None:
    cabeza = contenido[:4096].decode("ascii", errors="ignore")
    coincide = re.search(r"<meta[^>]+charset\s*=\s*[\"']?\s*([\w.\-:]+)", cabeza, re.IGNORECASE)
    return coincide.group(1).lower() if coincide else None


def _decodificar(contenido: bytes, codificacion: str | None) -> str:
    """Orden: la de la cabecera, la del `<meta>`, UTF-8 estricto y Windows-1252. Un nombre desconocido no falla."""
    candidatas = [codificacion, _declarada(contenido), "utf-8"]
    for nombre in candidatas:
        if not nombre:
            continue
        try:
            codecs.lookup(nombre)
            return contenido.decode(nombre)
        except (LookupError, UnicodeDecodeError):
            continue
    return contenido.decode("cp1252", errors="replace")


def _analizar(contenido: bytes | str, codificacion: str | None):
    texto = _decodificar(contenido, codificacion) if isinstance(contenido, bytes) else contenido
    texto = re.sub(r"^\s*<\?xml[^>]*\?>", "", texto)  # lxml no acepta una declaración de codificación en un texto
    if not texto.strip():
        return None
    try:
        return lhtml.document_fromstring(texto)
    except (etree.ParserError, ValueError):
        return None


# ---------- título ----------


def _quitar_sufijo_del_sitio(titulo: str, url_base: str) -> str:
    anfitrion = unicodedata.normalize("NFKD", (urlsplit(url_base).hostname or "").lower())
    for separador in SEPARADORES_DE_TITULO:
        if separador not in titulo:
            continue
        principal, _, sufijo = titulo.rpartition(separador)
        palabras = [p for p in re.split(r"\W+", unicodedata.normalize("NFKD", sufijo.lower())) if len(p) >= 3]
        if principal.strip() and any(p in anfitrion for p in palabras):
            return principal.strip()
    return titulo


def _titulo(raiz, url_base: str) -> str:
    for meta in raiz.iter("meta"):
        if (meta.get("property") or "").lower() == "og:title" and _normalizar(meta.get("content") or ""):
            return _normalizar(meta.get("content"))
    for elemento in raiz.iter("title"):
        titulo = _normalizar(elemento.text_content())
        if titulo:
            return _quitar_sufijo_del_sitio(titulo, url_base)
    for elemento in raiz.iter("h1"):
        titulo = _normalizar(elemento.text_content())
        if titulo:
            return titulo
    return ""


# ---------- limpieza del árbol ----------


def _es_ruido_por_nombre(elemento) -> bool:
    clases = (elemento.get("class") or "").lower().split()
    identificador = (elemento.get("id") or "").strip().lower()
    return any(c in CLASES_DE_RUIDO for c in clases) or identificador in CLASES_DE_RUIDO


def _raiz_del_contenido(documento):
    """`main`, `[role=main]` o `article` si existen; si no, `body`. Devuelve (raíz, hay contenido principal)."""
    for consulta in ("//main", "//*[@role='main']", "//article"):
        encontrados = documento.xpath(consulta)
        if encontrados:
            return encontrados[0], True
    cuerpo = documento.find("body")
    return (cuerpo if cuerpo is not None else documento), False


def _limpiar(raiz, hay_principal: bool) -> None:
    fuera = SIEMPRE_FUERA | (FUERA_EN_CONTENIDO if hay_principal else FUERA_SIN_CONTENIDO_PRINCIPAL)
    for elemento in list(raiz.iter()):
        if elemento is raiz or elemento.getparent() is None:
            continue
        etiqueta = elemento.tag if isinstance(elemento.tag, str) else None
        if etiqueta is None:
            # Comentarios e instrucciones: se quitan conservando su cola.
            _quitar(elemento)
        elif etiqueta in fuera or _es_ruido_por_nombre(elemento):
            _quitar(elemento)


def _quitar(elemento) -> None:
    """Quita el elemento y sus hijos, pero conserva el texto que viene después de él."""
    padre = elemento.getparent()
    if padre is None:
        return
    cola = elemento.tail
    anterior = elemento.getprevious()
    padre.remove(elemento)
    if cola:
        if anterior is not None:
            anterior.tail = (anterior.tail or "") + cola
        else:
            padre.text = (padre.text or "") + cola


# ---------- recorrido ----------


class _Escritor:
    def __init__(self, url_base: str):
        self.url_base = url_base

    def enlace(self, elemento, texto: str) -> str:
        texto = _normalizar(texto)
        destino = (elemento.get("href") or "").strip()
        if not destino or destino.startswith("#"):
            return texto
        absoluta = urljoin(self.url_base, destino)
        if urlsplit(absoluta).scheme.lower() not in ("http", "https"):
            return texto
        if not texto:
            return ""  # un enlace sin texto (solo una imagen) no deja una dirección suelta
        if texto.rstrip("/") == absoluta.rstrip("/"):
            return texto
        return f"{texto} ({absoluta})"

    def en_linea(self, elemento) -> str:
        """El texto de un elemento en línea (con sus hijos), con `\\n` donde hay un salto de línea."""
        partes = [elemento.text or ""]
        for hijo in elemento:
            partes.append(self._hijo_en_linea(hijo))
            partes.append(hijo.tail or "")
        texto = "".join(partes)
        if elemento.tag == "a":
            return self.enlace(elemento, texto)
        return texto

    def _hijo_en_linea(self, hijo) -> str:
        if hijo.tag == "br":
            return "\n"
        return self.en_linea(hijo)

    def lineas(self, elemento, nivel: int) -> list[tuple[bool, str]]:
        """Líneas del elemento como `(ya_formateada, texto)`: las de una lista anidada vienen con su viñeta y su sangría."""
        salida: list[tuple[bool, str]] = []
        pendiente: list[str] = [elemento.text or ""]

        def vaciar() -> None:
            salida.extend((False, linea) for linea in _lineas_de("".join(pendiente)))
            pendiente.clear()

        for hijo in elemento:
            etiqueta = hijo.tag
            if etiqueta in ("ul", "ol"):
                vaciar()
                salida.extend(self.lista(hijo, nivel))
            elif etiqueta == "table":
                vaciar()
                salida.extend((False, linea) for linea in self.tabla(hijo))
            elif etiqueta in ENCABEZADOS:
                vaciar()
                salida.extend((False, linea) for linea in _lineas_de(self.en_linea(hijo)))
            elif etiqueta in BLOQUES or self._tiene_bloques(hijo):
                vaciar()
                salida.extend(self.lineas(hijo, nivel))
            else:
                pendiente.append(self._hijo_en_linea(hijo))
            pendiente.append(hijo.tail or "")
        vaciar()
        return salida

    @staticmethod
    def _tiene_bloques(elemento) -> bool:
        return any(d.tag in BLOQUES or d.tag in ("ul", "ol", "table") for d in elemento.iterdescendants())

    def lista(self, lista, nivel: int) -> list[tuple[bool, str]]:
        salida: list[tuple[bool, str]] = []
        for item in lista:
            if item.tag in ("ul", "ol"):  # una lista anidada directamente dentro de otra
                salida.extend(self.lista(item, nivel + 1))
                continue
            if item.tag != "li":
                continue
            contenido = self.lineas(item, nivel + 1)
            primera = True
            for formateada, texto in contenido:
                if formateada:
                    salida.append((True, texto))
                elif SOLO_VINETA.match(texto):
                    continue
                elif primera:
                    salida.append((True, "  " * nivel + "- " + texto))
                    primera = False
                else:
                    salida.append((True, "  " * (nivel + 1) + texto))
        return salida

    def tabla(self, tabla) -> list[str]:
        filas = []
        for fila in tabla.iter("tr"):
            if self._tabla_mas_cercana(fila) is not tabla:
                continue
            celdas = []
            for celda in fila:
                if celda.tag in ("td", "th"):
                    texto = _normalizar(self.en_linea(celda).replace("\n", " "))
                    celdas.append(texto or None)
            filas.append((len(filas) + 1, celdas))
        lineas, *_ = lineas_de_tabla("", "la tabla", filas, 0, 1_000_000)
        return lineas

    @staticmethod
    def _tabla_mas_cercana(elemento):
        for ancestro in elemento.iterancestors():
            if ancestro.tag == "table":
                return ancestro
        return None


def _limpiar_lineas(lineas: list[str]) -> list[str]:
    """Sin líneas vacías, viñetas huérfanas ni líneas duplicadas seguidas."""
    salida: list[str] = []
    for linea in lineas:
        if not linea.strip() or SOLO_VINETA.match(linea.strip()):
            continue
        if salida and salida[-1] == linea:
            continue
        salida.append(linea.rstrip())
    return salida


def extraer(contenido: bytes | str, url_base: str, codificacion: str | None = None) -> Extraido:
    """El título y el texto de una página. `url_base` es la dirección final de la página (resuelve los enlaces relativos)."""
    documento = _analizar(contenido, codificacion)
    if documento is None:
        return Extraido("", "")
    titulo = _titulo(documento, url_base)
    raiz, hay_principal = _raiz_del_contenido(documento)
    _limpiar(raiz, hay_principal)
    escritor = _Escritor(url_base)
    lineas = [texto for _, texto in escritor.lineas(raiz, 0)]
    return Extraido(titulo, "\n".join(_limpiar_lineas(lineas)))


# ---------- nombre y documento ----------


def _limpiar_nombre(nombre: str | None) -> str:
    texto = _normalizar(nombre or "")[:NOMBRE_MAX].strip()
    return re.sub(r"\.web$", "", texto, flags=re.IGNORECASE).strip()


def nombre_del_documento(nombre_propio: str | None, titulo: str | None, url_final: str) -> str:
    """El nombre que se cita como fuente: el propio (recortado a 200 caracteres sin error), si no el título de la página y,
    si tampoco hay, el sitio."""
    for candidato in (nombre_propio, titulo):
        nombre = _limpiar_nombre(candidato)
        if nombre:
            return nombre
    return urlsplit(url_final).hostname or "Página web"


def fecha_larga(momento: datetime) -> str:
    """`20 de noviembre de 2026`, en la zona horaria configurada. Un momento sin zona se toma como UTC (así se guardan)."""
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=UTC)
    local = momento.astimezone(ZoneInfo(settings.cap_timezone))
    return f"{local.day} de {MESES[local.month - 1]} de {local.year}"


def armar_documento(url_final: str, nombre: str, texto: str, ahora: datetime) -> str:
    """El texto que se guarda y se ingesta: primero de dónde y cuándo se leyó, luego el nombre y el contenido."""
    return f"Fuente: {url_final} (consultada el {fecha_larga(ahora)})\n{nombre}\n\n{texto}"
