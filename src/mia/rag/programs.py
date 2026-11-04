"""El programa de un documento, para la aclaración del bot (feature 013, specs/013-aclaracion-programa-contexto/).

No hay un campo "programa" en la base: se toma del **título** del documento, que es su primera línea con la forma
`<PROGRAMA>: <SECCIÓN>` (por ejemplo `MAESTRÍA EN CIBERSEGURIDAD: ADMISIÓN`). De ahí salen dos cosas: el nombre natural,
que se muestra a la persona, y una clave de comparación, que decide si dos documentos son del mismo programa. Un documento
sin título con esa forma no tiene programa y no cuenta. Todo es por reglas de texto: ningún modelo de lenguaje.
"""

import logging
import re
import unicodedata
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

MIN_LABEL_CHARS = 3
MAX_LABEL_CHARS = 120

# Palabras de enlace que quedan en minúscula en el nombre natural (salvo la primera palabra).
LINK_WORDS = frozenset({"en", "de", "del", "la", "el", "los", "las", "y", "e", "con", "para", "a", "por"})
# Palabras que no distinguen a un programa de otro y se quitan de su clave.
KEY_STOP_WORDS = frozenset({"maestria", "en", "de", "del", "la", "el", "y", "los", "las"})

_WORD = re.compile(r"[^\W\d_]+")

# Palabras de la pregunta que no aportan evidencia: interrogativos, palabras vacías y palabras genéricas de un programa.
IGNORED_WORDS = frozenset(
    ["cuando", "cuanto", "cuanta", "cuantos", "cuantas", "esto", "eso", "aquel", "aquella", "aquello", "como", "donde", "quien", "quienes", "cual", "cuales", "porque", "para", "puedo", "puede", "pueden", "debo", "hay", "tiene", "tienen", "existe", "sobre", "desde", "hasta", "entre", "esta", "este", "estos", "estas", "esos", "esas", "algun", "alguna", "algunos", "algunas", "tengo", "quiero", "quisiera", "necesito", "favor", "hola", "gracias", "buenas", "buenos", "dias", "tardes", "noches", "informacion", "info", "saber", "ayuda", "dime", "dices", "maestria", "maestrias", "programa", "programas", "posgrado", "posgrados", "postgrado", "postgrados", "carrera", "carreras", "tec"]
)
MIN_EVIDENCE_WORD = 4
EVIDENCE_STEM = 6


@dataclass(frozen=True)
class Program:
    name: str  # nombre natural, el que ve la persona
    key: str  # clave de comparación: dos documentos con la misma clave son del mismo programa


@dataclass(frozen=True)
class ClarifyPolicy:
    """Con qué puntaje mínimo cuenta un fragmento para la aclaración, cuántos programas se listan como máximo y cuántos
    fragmentos mira la búsqueda de decisión."""

    min_similarity: float
    max_programs: int
    candidates: int = 30


@dataclass
class QueryExtras:
    """Lo que `run_query` entrega de más cuando lo pide el bot: los programas candidatos de una aclaración, y los
    documentos y los programas de las fuentes de una respuesta."""

    clarify: list[str] = field(default_factory=list)
    source_document_ids: list[str] = field(default_factory=list)
    programs: list[str] = field(default_factory=list)


def _strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def content_words(question: str) -> list[str]:
    """Las palabras de la pregunta que sirven de evidencia: minúsculas y sin tildes, de al menos 4 letras, sin repetir y sin
    interrogativos, palabras vacías ni palabras genéricas de un programa (`maestria`, `programa`...)."""
    words = re.sub(r"[^a-z0-9]+", " ", _strip_accents(question).lower()).split()
    return [w for w in dict.fromkeys(words) if len(w) >= MIN_EVIDENCE_WORD and w not in IGNORED_WORDS]


def has_evidence(text: str, words: list[str]) -> bool:
    """Si alguna palabra aparece al inicio de una palabra del texto (con sus primeros 6 caracteres: `postulo` coincide con
    `postularse`), sin importar tildes ni mayúsculas. Sin palabras no hay evidencia posible."""
    if not words:
        return False
    folded = _strip_accents(text).lower()
    pattern = r"\b(?:" + "|".join(re.escape(w[:EVIDENCE_STEM]) for w in words) + ")"
    return re.search(pattern, folded) is not None


def program_key(label: str) -> str:
    """Minúsculas, sin tildes ni signos y sin las palabras vacías: `Maestría en Ciberseguridad` da `ciberseguridad`."""
    words = re.sub(r"[^a-z0-9]+", " ", _strip_accents(label).lower()).split()
    return " ".join(w for w in words if w not in KEY_STOP_WORDS)


def natural_name(label: str) -> str:
    """Si la etiqueta está toda en mayúsculas, la pasa a mayúscula inicial por palabra con las palabras de enlace en
    minúscula; si ya trae minúsculas, la respeta tal cual."""
    label = label.strip()
    if label != label.upper():
        return label
    position = 0

    def convert(match: re.Match) -> str:
        nonlocal position
        word = match.group(0).lower()
        first = position == 0
        position += 1
        return word if word in LINK_WORDS and not first else word.capitalize()

    return _WORD.sub(convert, label)


def parse_title(text: str) -> str | None:
    """La etiqueta (antes de los dos puntos de la primera línea) o None si el texto no tiene la forma del título."""
    line = text.lstrip().split("\n", 1)[0] if text else ""
    index = line.find(":")
    if index < 0 or line[index + 1 : index + 3] == "//":  # sin dos puntos, o un enlace (https://...)
        return None
    label = line[:index].strip()
    if not MIN_LABEL_CHARS <= len(label) <= MAX_LABEL_CHARS or not re.search(r"[^\W\d_]", label):
        return None
    return label


# Programa de cada documento, por proceso. El id de un documento no se reutiliza, así que un documento eliminado deja
# una entrada inofensiva. Solo se guarda lo que se leyó con éxito: sin fragmento 0 o ante un fallo del almacén se vuelve
# a intentar la próxima vez.
_CACHE: dict[str, Program | None] = {}


def clear_cache() -> None:
    _CACHE.clear()


def program_of_document(vector_store, document_id: str) -> Program | None:
    """El programa de un documento por el título de su fragmento 0, o None si no lo tiene. Nunca lanza."""
    if document_id in _CACHE:
        return _CACHE[document_id]
    try:
        chunks = vector_store.get_chunks(document_id, [0])
    except Exception:
        logger.warning("No se pudo leer el título del documento %s para la aclaración", document_id, exc_info=True)
        return None
    if not chunks:
        return None
    try:
        label = parse_title(chunks[0].text)
    except (AttributeError, TypeError):  # un fragmento sin texto utilizable
        return None
    program = Program(natural_name(label), program_key(label)) if label else None
    if program is not None and not program.key:
        program = None
    _CACHE[document_id] = program
    return program


def group_by_program(
    results, vector_store, min_score: float, max_programs: int, evidence_words: list[str] | None = None
) -> list[Program]:
    """Los programas de los resultados con puntaje mínimo `min_score`, sin repetir, en el orden de su mejor resultado
    (los resultados llegan de mayor a menor puntaje) y como máximo `max_programs`. Los documentos sin programa no cuentan.
    Con `evidence_words` solo cuentan los fragmentos que traen alguna de esas palabras: el puntaje solo no distingue una
    pregunta ambigua de una sin relación (el modelo de embeddings comprime los puntajes entre 0,79 y 0,87)."""
    found: dict[str, Program] = {}
    for result in results:
        if result.score < min_score:
            continue
        if evidence_words is not None and not has_evidence(result.text, evidence_words):
            continue
        program = program_of_document(vector_store, result.document_id)
        if program is not None and program.key not in found:
            found[program.key] = program
            if len(found) >= max_programs:
                break
    return list(found.values())
