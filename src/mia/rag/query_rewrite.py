"""Pregunta limpia: segundo intento de búsqueda (feature 008).

Cuando la búsqueda normal no deja ningún fragmento sobre el umbral de similitud, una pregunta de
identificación o descripción ("¿Quién es X?", "¿Qué es el X?", "háblame de X") se reduce por reglas de texto a
lo que se busca ("X") y la búsqueda se repite una vez. No usa ningún modelo de lenguaje. Se enciende con
QUERY_CLEAN_QUESTION (on/off, apagada por defecto).

Las reglas solo reconocen preguntas de identificación o descripción: en "¿Cuántos créditos tiene X?" el resto
de la pregunta importa y quitarlo la dañaría, así que esas no se tocan. Ver
specs/008-pregunta-limpia/contracts/pregunta-limpia.md.
"""

import re
import unicodedata

from mia.rag.completeness import switch_enabled

SIGNS = "¿?¡!"
# Caracteres que se recortan de los extremos de la pregunta.
_EDGE = set(" .,;:" + SIGNS)
MIN_CHARS = 3
MAX_WORDS = 8
NOTE_MAX_CHARS = 120


def clean_question_enabled(value: str) -> bool:
    return switch_enabled(value, "QUERY_CLEAN_QUESTION")


# --- Reglas (sobre el texto normalizado: minúsculas y sin tildes) ------------------------------------------

# Cortesías que pueden anteceder a una envoltura; solo valen si después aparece una.
_COURTESIES = re.compile(
    r"^(?:"
    r"por favor"
    r"|(?:me\s+)?(?:puedes|podrias|puede|podria)\s+(?:decir|explicar|indicar|contar)(?:me)?"
    r"|dime"
    r"|(?:quiero|necesito|quisiera|me gustaria)\s+saber"
    r")(?=[\s,]|$)[\s,]*"
)
# "por favor" como palabra completa; "gracias" solo tras un signo de puntuación, para no recortar un apellido
# final ("Juan Gracias") ni el final de una palabra ("Desgracias").
_TRAILING_COURTESY = re.compile(r"(?:[\s,.;:?!¡¿]*(?<!\w)por favor|[,.;:?!][\s,.;:?!¡¿]*(?<!\w)gracias)$")

# Envolturas al inicio de la pregunta. Lo que sigue es el candidato.
_WRAPPERS = (
    # Identificación: "quién es X", "qué es el X", "qué significa X"
    re.compile(
        r"^(?:quien|quienes|que)\s+(?P<verbo>es|son|era|eran|fue|fueron|significa|significan)\s+"
        r"(?:(?:el|la|los|las|un|una)\s+)?"
    ),
    # Pedir información: "dame información sobre X"
    re.compile(
        r"^(?:dame|quiero|necesito|busco)\s+(?:toda\s+)?(?:la\s+)?(?:informacion|datos|detalles)\s+"
        r"(?:que\s+(?:haya|tengas|tenga)\s+)?(?:sobre|acerca\s+de|de)\s+"
    ),
    # Pedir que hable de algo: "háblame de X"
    re.compile(r"^(?:hablame|cuentame|explicame)\s+(?:de|sobre|acerca\s+de)\s+"),
    # "qué se sabe de X"
    re.compile(r"^que\s+(?:sabes|sabe|se\s+sabe)\s+(?:de|sobre|acerca\s+de)\s+"),
)

# Guardas del candidato: palabras que indican una cláusula o que la pregunta pide un dato y no un nombre.
_CLAUSE_WORDS = {"que", "cuando", "donde", "cuanto", "cuanta", "cuantos", "cuantas", "porque"}
_START_WORDS = {"lo", "que"} | {
    "necesario", "necesaria", "obligatorio", "obligatoria", "posible", "suficiente", "importante",
    "mejor", "igual", "diferente", "nuevo", "nueva",
}


# Tras un verbo en pasado, un participio ("fue designado", "fueron elegidas") es una voz pasiva: la pregunta
# pide un dato y no un nombre.
_PAST_VERBS = {"era", "eran", "fue", "fueron"}
_PARTICIPLE = re.compile(r"\w+(?:ado|ada|ados|adas|ido|ida|idos|idas)$")


def _fold(text: str) -> str:
    """Minúsculas y sin tildes, carácter por carácter: el resultado tiene la misma longitud que el original."""
    out = []
    for ch in text:
        base = unicodedata.normalize("NFD", ch)[0]
        low = base.lower()
        out.append(low if len(low) == 1 else base)
    return "".join(out)


def _es_igual(candidate: str, question: str) -> bool:
    """Si el candidato es igual a la pregunta, ambos normalizados."""
    return _fold(candidate).strip(" ".join(_EDGE)) == _fold(question).strip(" ".join(_EDGE))


def _trim(folded: str, start: int, end: int) -> tuple[int, int]:
    while start < end and folded[start] in _EDGE:
        start += 1
    while end > start and folded[end - 1] in _EDGE:
        end -= 1
    return start, end


def clean_question(question: str) -> str | None:
    """La pregunta reducida a lo que se busca, con su escritura original, o None si no hay segundo intento."""
    original = " ".join((question or "").split())
    if not original:
        return None
    folded = _fold(original)
    start, end = _trim(folded, 0, len(original))

    # Cortesías finales ("por favor", "gracias"), antes de revisar que sea una sola pregunta.
    while True:
        match = _TRAILING_COURTESY.search(folded, start, end)
        if not match:
            break
        end = match.start()
        start, end = _trim(folded, start, end)
    if start >= end or any(ch in SIGNS for ch in folded[start:end]):
        return None

    # Hasta dos cortesías iniciales.
    for _ in range(2):
        match = _COURTESIES.match(folded[start:end])
        if not match:
            break
        start += match.end()
        start, end = _trim(folded, start, end)

    # Una envoltura; si ninguna aplica no hay segundo intento.
    for wrapper in _WRAPPERS:
        match = wrapper.match(folded[start:end])
        if match:
            candidate_start = start + match.end()
            past = match.groupdict().get("verbo") in _PAST_VERBS
            break
    else:
        return None

    candidate_start, end = _trim(folded, candidate_start, end)
    candidate = original[candidate_start:end]
    candidate_folded = folded[candidate_start:end]

    # Guardas del candidato.
    if len(candidate) < MIN_CHARS or _es_igual(candidate, original):
        return None
    words = re.findall(r"\w+", candidate_folded)
    if not words or len(words) > MAX_WORDS:
        return None
    if words[0] in _START_WORDS or any(word in _CLAUSE_WORDS for word in words):
        return None
    if past and _PARTICIPLE.match(words[0]):
        return None
    if any(ch in SIGNS for ch in candidate):
        return None
    return candidate


def clean_note(text: str, found: bool) -> str:
    """Nota para el registro de Uso (`reject_reason`) de una consulta con segundo intento."""
    resultado = "con resultados" if found else "sin resultados"
    return f"Pregunta limpia: «{text[:NOTE_MAX_CHARS]}» ({resultado})"
