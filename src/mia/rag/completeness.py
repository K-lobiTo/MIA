"""Respuestas completas y sin cortes (feature 007).

Dos mecanismos independientes, cada uno detrás de su variable de entorno y apagado por defecto:

- QUERY_COMPLETE_CONTEXT: para el documento principal de la consulta se entrega el documento completo si
  es de tamaño moderado, o se prolonga hacia adelante el fragmento encontrado; lo que no llega al final del
  documento se marca con `[...el documento continúa]` y una instrucción le pide al modelo decirlo.
- QUERY_RETRY_CUT_ANSWERS: si el modelo termina la generación de forma anormal (límite de longitud u otro
  motivo), se reintenta una vez respetando los topes de gasto y, si vuelve a cortarse, se entrega el texto
  con un aviso.

Ver specs/007-respuestas-completas/contracts/contexto-completo-y-cortes.md.
"""

import logging

logger = logging.getLogger(__name__)

_VALORES_ENCENDIDO = {"on", "true", "1", "yes"}
_VALORES_APAGADO = {"off", "false", "0", "no", ""}
# (variable, valor) inválidos ya avisados en este proceso: el aviso sale una sola vez, no en cada consulta.
_INVALID_VALUES_WARNED: set[tuple[str, str]] = set()


def switch_enabled(value: str, variable: str) -> bool:
    """Si una opción de encendido (on/off) está encendida. Un valor inválido se trata como apagado y avisa una vez."""
    normalizado = (value or "").strip().lower()
    if normalizado in _VALORES_ENCENDIDO:
        return True
    clave = (variable, normalizado)
    if normalizado not in _VALORES_APAGADO and clave not in _INVALID_VALUES_WARNED:
        _INVALID_VALUES_WARNED.add(clave)
        logger.warning("%s tiene un valor inválido (%r): se trata como apagado. Usar on u off.", variable, value)
    return False


def complete_context_enabled(value: str) -> bool:
    return switch_enabled(value, "QUERY_COMPLETE_CONTEXT")


def retry_cut_enabled(value: str) -> bool:
    return switch_enabled(value, "QUERY_RETRY_CUT_ANSWERS")


# Línea que se agrega, solo en el texto que ve el modelo, a un pasaje al que le siguen fragmentos del documento
# que no se entregaron.
CONTINUES_MARKER = "[...el documento continúa]"

# Párrafo que se agrega a las instrucciones del modo cuando QUERY_COMPLETE_CONTEXT está encendida.
COMPLETENESS_INSTRUCTIONS = (
    "Si la respuesta es una lista o una sección y el fragmento termina con la marca "
    f"{CONTINUES_MARKER}, indica al final de tu respuesta, en una línea aparte, que la lista puede continuar "
    "en ese documento y nómbralo. No escribas esa advertencia si el fragmento no lleva la marca."
)


def mark_continuation(text: str, continues: bool) -> str:
    """El texto del pasaje con la marca de continuación como última línea, si el documento continúa."""
    return f"{text}\n{CONTINUES_MARKER}" if continues else text


# --- Reintento de respuestas cortadas ------------------------------------------------------------------

CUT_NOTICE = "Aviso: la respuesta pudo quedar incompleta."
# Notas que quedan en el registro de Uso (campo reject_reason) en las consultas respondidas con un corte.
NOTE_RETRIED = "Respuesta cortada: se reintentó"
NOTE_NOTICE = "Respuesta cortada: se entregó con aviso"


def needs_retry(finish_reason: str | None, is_no_info: bool) -> bool:
    """Si una generación terminó de forma anormal y vale la pena reintentarla. Un motivo desconocido (el
    proveedor no lo informa) o una respuesta "sin información" no se reintentan."""
    return finish_reason in ("length", "other") and not is_no_info


def with_notice(text: str) -> str:
    """El texto con el aviso de posible corte como última línea (sin repetirlo)."""
    if text.rstrip().endswith(CUT_NOTICE):
        return text
    return f"{text.rstrip()}\n\n{CUT_NOTICE}"


def _sum[T: (int, float)](a: T | None, b: T | None) -> T | None:
    return None if a is None and b is None else (a or 0) + (b or 0)


def merge_attempts(first, second):
    """Un solo LLMAnswer con el texto y el motivo de fin del segundo intento y el uso (tokens y costo) de los
    dos. Los datos nulos cuentan como cero; si ninguno de los dos informa un dato, queda nulo."""
    from dataclasses import replace

    return replace(
        second,
        model=second.model or first.model,
        prompt_tokens=_sum(first.prompt_tokens, second.prompt_tokens),
        completion_tokens=_sum(first.completion_tokens, second.completion_tokens),
        reasoning_tokens=_sum(first.reasoning_tokens, second.reasoning_tokens),
        cost_usd=_sum(first.cost_usd, second.cost_usd),
    )


def combine_notes(*notes: str | None) -> str | None:
    """Une con "; " las notas que no son nulas; nulo si no hay ninguna."""
    presentes = [n for n in notes if n]
    return "; ".join(presentes) if presentes else None
