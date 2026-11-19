"""Identificadores de los modos de respuesta y qué modos comparten el trato del razonamiento. Vive aparte de `modes.py` para
que `history.py` (que importa `modes.py` indirectamente por `llm.py`) pueda usarlo sin un ciclo de importaciones."""

LITERAL = "literal"
RAZONAMIENTO = "razonamiento"
PLANTILLA = "plantilla"
MODE_IDS = [LITERAL, RAZONAMIENTO, PLANTILLA]

# El modo plantilla usa el mismo modelo, esfuerzo y precios que el razonamiento: donde el razonamiento tiene un trato propio
# (topes, historial, avisos), la plantilla recibe el mismo (feature 020).
REASONING_CLASS = (RAZONAMIENTO, PLANTILLA)


def is_reasoning_class(mode: str | None) -> bool:
    """Verdadero para el modo con razonamiento y para el modo plantilla, que se apoya en él."""
    return mode in REASONING_CLASS
