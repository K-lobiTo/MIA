"""El historial de una consulta (feature 014, specs/014-memoria-conversacion/).

El cliente (la Consulta administrativa) envía las vueltas anteriores de su conversación; aquí se valida, se recorta y se
convierte en el bloque que el modelo recibe antes del contexto. **El historial nunca es una fuente de datos**: sirve solo para
entender la pregunta. Nada de esto se guarda: vive lo que dura la consulta."""

from dataclasses import dataclass

from mia.config import settings

# Texto con que la API responde "sin información" (el de `NO_INFO_ANSWER` de la ruta de consulta) y marcador del modelo.
NO_INFO_PREFIX = "No encontré información suficiente"
NO_INFO_MARKER = "SIN_INFORMACION"

HISTORY_HEADER = (
    "Conversación anterior (solo para entender la pregunta; no es una fuente de datos):"
)
REASONING_WARNING = "(respuesta del modo con razonamiento: puede incluir cálculos o inferencias que no dicen los documentos)"

# El modo con razonamiento recupera más fragmentos y usa modelos de contexto mayor: admite el doble de historial.
REASONING_FACTOR = 2


@dataclass(frozen=True)
class HistoryTurn:
    """Una vuelta de la conversación: la pregunta, su respuesta y, si se sabe, el modo en que se respondió."""

    question: str
    answer: str
    mode: str | None = None


def _is_no_info(answer: str) -> bool:
    text = answer.strip()
    return text.strip(".").upper() == NO_INFO_MARKER or text.startswith(NO_INFO_PREFIX)


def sanitize_history(history, turns: int, mode: str) -> list[HistoryTurn]:
    """Las vueltas que se usan: con `turns` en 0 ninguna (ni se mira la entrada); si no, las últimas `turns` vueltas válidas
    (se descartan las vacías y las de "sin información"), con cada pregunta y respuesta recortadas y el total acotado por modo
    (si se pasa, salen las más viejas)."""
    if turns <= 0:
        return []
    factor = REASONING_FACTOR if mode == "razonamiento" else 1
    max_answer = settings.history_max_answer_chars * factor
    max_total = settings.history_max_chars * factor
    valid: list[HistoryTurn] = []
    for turn in history or []:
        question, answer = (turn.question or "").strip(), (turn.answer or "").strip()
        if not question or not answer or _is_no_info(answer):
            continue
        valid.append(
            HistoryTurn(
                question[: settings.history_max_question_chars],
                answer[:max_answer],
                getattr(turn, "mode", None),
            )
        )
    valid = valid[-turns:]
    while valid and sum(len(t.question) + len(t.answer) for t in valid) > max_total:
        valid.pop(0)
    return valid


def format_history(history: list[HistoryTurn] | None) -> str:
    """El bloque rotulado que va antes del contexto en el mensaje de usuario; vacío sin vueltas."""
    if not history:
        return ""
    entries = []
    for turn in history:
        lines = [f"Pregunta: {turn.question}", f"Respuesta: {turn.answer}"]
        if turn.mode == "razonamiento":
            lines.append(REASONING_WARNING)
        entries.append("\n".join(lines))
    return HISTORY_HEADER + "\n" + "\n\n".join(entries)
