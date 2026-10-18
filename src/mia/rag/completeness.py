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
