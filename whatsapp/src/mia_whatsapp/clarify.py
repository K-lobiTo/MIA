"""Reglas puras de la aclaración de programa (feature 013, specs/013-aclaracion-programa-contexto/).

Sin modelo de lenguaje: comparar la respuesta de la persona con los programas que el bot le ofreció, componer la pregunta
con el programa elegido y armar el texto de la aclaración. Este servicio no importa `mia`, así que las reglas de
normalización (las mismas de la API, `mia.rag.programs`) están escritas aquí.
"""

import re
import unicodedata

# Palabras que no distinguen a un programa de otro (las mismas que la clave del programa en la API).
STOP_WORDS = frozenset({"maestria", "en", "de", "del", "la", "el", "y", "los", "las"})


def _strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def _stem(word: str) -> str:
    """El plural simple no distingue: "negocios" y "negocio" son la misma palabra."""
    return word[:-1] if len(word) > 3 and word.endswith("s") else word


def key_words(text: str) -> frozenset[str]:
    """Las palabras que identifican: minúsculas, sin tildes ni signos, sin palabras vacías y sin plural simple."""
    words = re.sub(r"[^a-z0-9]+", " ", _strip_accents(text).lower()).split()
    return frozenset(_stem(w) for w in words if w not in STOP_WORDS)


def match_candidate(text: str, candidates: list[str]) -> str | None:
    """El candidato que nombra la persona, o None si no se puede decidir (ninguno o más de uno, o nada que comparar).

    Un candidato coincide si **todas** las palabras del mensaje están en las suyas ("la de analítica" coincide con la
    Maestría en Analítica de Negocio). Un número coincide con la opción de esa posición (`1`, `2`)."""
    stripped = text.strip()
    if re.fullmatch(r"\d{1,2}", stripped):
        position = int(stripped)
        return candidates[position - 1] if 1 <= position <= len(candidates) else None
    words = key_words(stripped)
    if not words:
        return None
    matches = [candidate for candidate in candidates if words <= key_words(candidate)]
    return matches[0] if len(matches) == 1 else None


# Palabras (ya sin tildes ni plural simple) con las que una persona dice "los dos": un mensaje hecho solo de ellas los nombra a todos.
_ALL_WORDS = frozenset({"dos", "ambo", "amba", "todo", "toda", "opcion", "opcione", "programa"})


def names_several(text: str, candidates: list[str]) -> bool:
    """Si la respuesta nombra a más de un candidato ("ciberseguridad y analítica") o a todos ("las dos", "ambas"): no se puede
    decidir. Una palabra que comparten todos los candidatos no distingue a ninguno y no cuenta; "todo" dentro de una frase que
    nombra a un solo programa tampoco ("dime todo de ciberseguridad"): solo cuenta un mensaje hecho de esas palabras."""
    stripped = text.strip()
    if not candidates or re.fullmatch(r"\d{1,2}", stripped):
        return False
    words = key_words(stripped)
    if not words:
        return False
    if words <= _ALL_WORDS:
        return True
    key_sets = [key_words(candidate) for candidate in candidates]
    common = frozenset.intersection(*key_sets)
    return sum(1 for keys in key_sets if words & (keys - common)) >= 2


def with_program(question: str, program: str) -> str:
    """La pregunta con el programa al final, como la escribiría una persona: `¿Cuánto cuesta? (Maestría en X)`."""
    return f"{question.strip()} ({program})"


def render_clarify(text: str, candidates: list[str]) -> str:
    """El texto de la aclaración con la lista numerada de programas. `{programs}` marca dónde va la lista; si el texto
    configurado no lo trae, la lista se agrega al final para que nunca se pierda."""
    listing = "\n".join(f"{position}. {name}" for position, name in enumerate(candidates, start=1))
    if "{programs}" in text:
        return text.replace("{programs}", listing)
    return f"{text}\n{listing}"
