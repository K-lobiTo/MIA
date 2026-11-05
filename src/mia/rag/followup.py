"""Seguimientos: usar el historial también para buscar los documentos (feature 014, specs/014-memoria-conversacion/).

Una pregunta de seguimiento ("¿y cuánto cuesta?") no dice de qué se habla: buscada sola no encuentra fragmentos y la consulta
se corta en "sin información" antes de llegar al modelo. Con historial vigente, un seguimiento se reformula con lo que se venía
hablando. Hay tres estrategias, elegidas por `HISTORY_REFORMULATION`: `rules` (juntar las preguntas anteriores con la actual,
sin ningún modelo), `model` (una llamada corta que reescribe la pregunta) y `off` (no se reformula). Una pregunta que se
entiende sola nunca se toca."""

import logging
import re
import unicodedata
from dataclasses import dataclass

from mia.config import settings
from mia.rag.history import HistoryTurn
from mia.rag.llm import get_llm_provider
from mia.rag.modes import LITERAL, estimate_cost, mode_config
from mia.rag.programs import content_words

logger = logging.getLogger(__name__)

STRATEGIES = ("rules", "model", "off")
DEFAULT_STRATEGY = "rules"
_WARNED: set[str] = set()

# Una pregunta de pocas palabras sin tema propio (como "¿cuánto cuesta?") o que continúa lo anterior es un seguimiento.
SHORT_QUESTION_WORDS = 3
SHORT_QUESTION_CONTENT = 2
CONTINUATION_WORDS = frozenset({"y", "pero", "entonces", "tambien", "ademas"})
REFERENCE_WORDS = frozenset(
    {
        "eso", "esto", "esa", "ese", "esas", "esos", "ello", "aquel", "aquella", "anterior", "mismo", "misma", "primero",
        "primera", "segundo", "segunda", "tercero", "tercera", "ultimo", "ultima", "ahi", "alli", "dicho", "dicha",
    }
)  # fmt: skip

# Cuántas preguntas anteriores se juntan con la actual y el largo máximo del texto de búsqueda.
PREVIOUS_QUESTIONS = 2
MAX_SEARCH_CHARS = 400


def strategy(value: str | None = None) -> str:
    """La estrategia de reformulación (la de la configuración si no se da). Un valor inválido es `rules` y avisa una vez."""
    raw = settings.history_reformulation if value is None else value
    normalized = (raw or "").strip().lower()
    if normalized in STRATEGIES:
        return normalized
    if normalized not in _WARNED:
        _WARNED.add(normalized)
        logger.warning(
            "HISTORY_REFORMULATION tiene un valor inválido (%r): se trata como rules. Usar rules, model u off.",
            raw,
        )
    return DEFAULT_STRATEGY


def _words(text: str) -> list[str]:
    folded = "".join(
        c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn"
    ).lower()
    return re.sub(r"[^a-z0-9]+", " ", folded).split()


def is_followup(question: str, history: list[HistoryTurn] | None) -> bool:
    """Si la pregunta necesita el historial para entenderse: hay historial y la pregunta continúa lo anterior (empieza con
    "y", "pero", "entonces"), se refiere a ello ("eso", "el segundo", "anterior") o es tan corta que no trae tema propio."""
    if not history:
        return False
    words = _words(question)
    if not words:
        return False
    if words[0] in CONTINUATION_WORDS or any(w in REFERENCE_WORDS for w in words):
        return True
    return (
        len(words) <= SHORT_QUESTION_WORDS
        and len(content_words(question)) <= SHORT_QUESTION_CONTENT
    )


def rules_question(question: str, history: list[HistoryTurn]) -> str:
    """La pregunta de búsqueda por reglas: las últimas dos preguntas anteriores y la actual, hasta 400 caracteres. Lo que
    sobra se corta por el inicio de las anteriores (sin dejar una palabra a medias); la actual nunca se corta."""
    budget = MAX_SEARCH_CHARS - len(question) - 1
    if budget <= 0 or not history:
        return question
    previous = " ".join(turn.question for turn in history[-PREVIOUS_QUESTIONS:])
    if len(previous) > budget:
        cut = previous[-budget:]
        if not previous[
            -budget - 1
        ].isspace():  # el corte cayó dentro de una palabra: se descarta la parte a medias
            cut = cut.split(" ", 1)[1] if " " in cut else ""
        previous = cut
    return f"{previous} {question}".strip()


# Largo aceptable de una pregunta reescrita por el modelo (una línea).
REWRITE_MIN_CHARS = 5
REWRITE_MAX_CHARS = 300


@dataclass
class Reformulation:
    """La pregunta con que se busca y cómo se obtuvo: `used` es "none" (la pregunta tal cual), "rules" o "model". Con el
    modelo trae también el costo y los tokens de la reescritura, para sumarlos a la consulta."""

    text: str
    used: str = "none"
    cost_usd: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0


def _valid_rewrite(text: str) -> str | None:
    """La reescritura limpia, o None si no sirve: vacía, de varias líneas, muy corta o muy larga."""
    cleaned = (text or "").strip().strip("\"'«»").strip()
    if "\n" in cleaned or not REWRITE_MIN_CHARS <= len(cleaned) <= REWRITE_MAX_CHARS:
        return None
    return cleaned


def _model_question(question: str, history: list[HistoryTurn]) -> Reformulation | None:
    """La reformulación con el modelo del modo literal, o None (con un aviso sin el texto) si no se pudo."""
    config = mode_config(LITERAL)
    if config is None:
        logger.warning(
            "Reescritura con el modelo no disponible (el modo literal no está configurado): se usan las reglas."
        )
        return None
    try:
        provider = get_llm_provider(config.provider, config.model, "")
        answer = provider.rewrite(question, history)
    except NotImplementedError:
        logger.warning(
            "El proveedor del modo literal no implementa la reescritura de preguntas: se usan las reglas."
        )
        return None
    except Exception:
        logger.warning(
            "Falló la reescritura de la pregunta con el modelo: se usan las reglas.", exc_info=True
        )
        return None
    # La llamada se cobró aunque su resultado no sirva: el costo se suma a la consulta de todos modos.
    cost = (
        float(answer.cost_usd)
        if answer.cost_usd is not None
        else float(estimate_cost(LITERAL, answer.prompt_tokens, answer.completion_tokens))
    )
    rewritten = _valid_rewrite(answer.text)
    if rewritten is None:
        if answer.finish_reason == "length":
            logger.warning(
                "La reescritura del modelo se cortó por el límite de tokens (HISTORY_REWRITE_MAX_TOKENS, hoy %d): "
                "un modelo de razonamiento gasta casi todo pensando. Se usan las reglas.",
                settings.history_rewrite_max_tokens,
            )
        else:
            logger.warning(
                "La reescritura del modelo no es válida (vacía, de varias líneas o de largo inusual): se usan las reglas."
            )
        return Reformulation("", "invalid", cost, answer.prompt_tokens or 0, answer.completion_tokens or 0)
    return Reformulation(
        rewritten, "model", cost, answer.prompt_tokens or 0, answer.completion_tokens or 0
    )


def search_question(
    question: str, history: list[HistoryTurn] | None, chosen: str | None = None
) -> Reformulation:
    """El texto con el que se busca: la pregunta tal cual si se entiende sola, no hay historial o la estrategia es `off`;
    si es un seguimiento, la reformulada por la estrategia (`rules` o `model`; el modelo cae a las reglas si falla)."""
    selected = strategy(chosen)
    if not history or selected == "off" or not is_followup(question, history):
        return Reformulation(question)
    if selected == "model":
        result = _model_question(question, history)
        if result is not None and result.used == "model":
            return result
        if result is not None:
            # Reescritura inválida: se busca con las reglas, pero lo que costó la llamada cuenta.
            return Reformulation(
                rules_question(question, history),
                "rules",
                result.cost_usd,
                result.prompt_tokens,
                result.completion_tokens,
            )
    return Reformulation(rules_question(question, history), "rules")
