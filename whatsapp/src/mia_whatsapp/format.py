"""Formato del texto que se envía por WhatsApp (funciones puras, sin red ni estado).

El modo literal responde en Markdown (encabezados, listas, tablas, negritas); WhatsApp tiene su propio formato
(`*negrita*`, `_cursiva_`, `~tachado~`, listas con guion) y no entiende el resto. Aquí se convierte, se compone el mensaje
(saludo, respuesta y fuentes en un solo mensaje, para no gastar cuota) y se parte lo que excede el tamaño de un mensaje.
Ver specs/011-bot-whatsapp-kapso/research.md R10.
"""

import re

# Margen bajo el límite de 4.096 caracteres de un mensaje de WhatsApp.
MESSAGE_LIMIT = 4000
MAX_SOURCES = 3

_CODE_BLOCK = re.compile(r"(```.*?```)", re.DOTALL)
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$")
_RULE = re.compile(r"^\s*([-*_])(\s*\1){2,}\s*$")
_BULLET = re.compile(r"^(\s*)[*+-]\s+")
_TABLE_SEPARATOR_CELL = re.compile(r"^:?-{3,}:?$")
_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)\)")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_BOLD = re.compile(r"\*\*(.+?)\*\*|__(.+?)__")
_ITALIC = re.compile(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])")
_STRIKE = re.compile(r"~~(.+?)~~")
_BLANK_LINES = re.compile(r"\n{3,}")
_TRAILING_SPACES = re.compile(r"[ \t]+\n")

# Marcas internas de la negrita ya convertida: así la conversión de la cursiva no la toca.
_BOLD_OPEN, _BOLD_CLOSE = "\x01", "\x02"


def _table_cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _convert_table(rows: list[str]) -> list[str]:
    """Una tabla de Markdown pasa a una fila de texto por línea (celdas unidas con " - "); si tiene encabezado, este va en
    negrita. La línea de guiones que separa el encabezado se quita."""
    cells = [_table_cells(row) for row in rows]
    has_header = len(cells) > 1 and all(_TABLE_SEPARATOR_CELL.match(c) for c in cells[1] if c)
    lines = []
    for index, row in enumerate(cells):
        if all(_TABLE_SEPARATOR_CELL.match(c) for c in row if c) and any(row):
            continue
        text = " - ".join(c for c in row if c)
        if not text:
            continue
        lines.append(f"**{text}**" if has_header and index == 0 else text)
    return lines


def _convert_lines(segment: str) -> str:
    out: list[str] = []
    table: list[str] = []

    def flush_table() -> None:
        if table:
            out.extend(_convert_table(table))
            table.clear()

    for line in segment.split("\n"):
        if line.strip().startswith("|"):
            table.append(line)
            continue
        flush_table()
        if _RULE.match(line):
            out.append("")
            continue
        heading = _HEADING.match(line)
        if heading:
            inner = heading.group(1).replace("**", "").replace("__", "").strip()
            out.append(f"**{inner}**" if inner else "")
            continue
        out.append(_BULLET.sub(r"\1- ", line))
    flush_table()
    return "\n".join(out)


def _link_to_text(match: re.Match) -> str:
    text, url = match.group(1).strip(), match.group(2)
    return url if text == url or not text else f"{text} ({url})"


def _convert_inline(text: str) -> str:
    text = _IMAGE.sub(lambda m: f"{m.group(1).strip()} ({m.group(2)})" if m.group(1).strip() else m.group(2), text)
    text = _LINK.sub(_link_to_text, text)
    text = _BOLD.sub(lambda m: f"{_BOLD_OPEN}{m.group(1) or m.group(2)}{_BOLD_CLOSE}", text)
    text = _ITALIC.sub(r"_\1_", text)
    text = _STRIKE.sub(r"~\1~", text)
    return text.replace(_BOLD_OPEN, "*").replace(_BOLD_CLOSE, "*")


def to_whatsapp(text: str) -> str:
    """Convierte Markdown al formato de WhatsApp: `**x**` a `*x*`, `*x*` a `_x_`, `~~x~~` a `~x~`, encabezados a una línea
    en negrita, enlaces a `texto (dirección)`, listas con guion, tablas a filas de texto y sin reglas horizontales. Los
    bloques de código quedan como están."""
    parts = _CODE_BLOCK.split(text)
    converted = [
        part if index % 2 == 1 else _convert_inline(_convert_lines(part)) for index, part in enumerate(parts)
    ]
    result = "".join(converted)
    result = _TRAILING_SPACES.sub("\n", result)
    return _BLANK_LINES.sub("\n\n", result).strip()


def format_sources(sources: list[str]) -> str:
    """`Fuentes: a.pdf, b.pdf`: los nombres sin repetir, hasta tres y `y N más` si hay más. Vacío sin fuentes."""
    names = list(dict.fromkeys(s.strip() for s in sources if s and s.strip()))
    if not names:
        return ""
    shown = names[:MAX_SOURCES]
    line = "Fuentes: " + ", ".join(shown)
    extra = len(names) - len(shown)
    return f"{line} y {extra} más" if extra > 0 else line


def compose_text(answer: str, sources: list[str], greeting: str | None) -> str:
    """El mensaje de una respuesta: saludo (si toca), respuesta en formato de WhatsApp y la línea de fuentes, todo en un
    solo mensaje (cada mensaje suma a la cuota mensual)."""
    parts = []
    if greeting and greeting.strip():
        parts.append(greeting.strip())
    body = to_whatsapp(answer)
    if body:
        parts.append(body)
    sources_line = format_sources(sources)
    if sources_line:
        parts.append(sources_line)
    return "\n\n".join(parts)


def _sentences(text: str) -> list[str]:
    return re.split(r"(?<=[.!?…])\s+", text)


# De lo más grueso a lo más fino: párrafos, líneas, oraciones y palabras; cada nivel con el separador con que se une.
_LEVELS = [
    (lambda t: t.split("\n\n"), "\n\n"),
    (lambda t: t.split("\n"), "\n"),
    (_sentences, " "),
    (lambda t: t.split(), " "),
]


def _split(text: str, limit: int, level: int = 0) -> list[str]:
    if len(text) <= limit:
        return [text]
    if level >= len(_LEVELS):
        # Una sola palabra más larga que un mensaje: no hay dónde cortar mejor.
        return [text[i : i + limit] for i in range(0, len(text), limit)]
    splitter, joiner = _LEVELS[level]
    chunks: list[str] = []
    current = ""
    for piece in (p.strip() for p in splitter(text)):
        if not piece:
            continue
        if len(piece) > limit:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_split(piece, limit, level + 1))
            continue
        candidate = piece if not current else current + joiner + piece
        if len(candidate) <= limit:
            current = candidate
        else:
            chunks.append(current)
            current = piece
    if current:
        chunks.append(current)
    return chunks


def split_message(text: str, limit: int = MESSAGE_LIMIT) -> list[str]:
    """Parte un texto en mensajes de hasta `limit` caracteres, en orden: por párrafos y, si un párrafo no cabe, por
    líneas, oraciones y palabras. Un texto corto queda en un solo mensaje; nunca devuelve partes vacías."""
    text = text.strip()
    if not text:
        return []
    return [chunk for chunk in _split(text, limit) if chunk]
