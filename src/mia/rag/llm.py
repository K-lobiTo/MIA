from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import lru_cache

from mia.rag.history import HistoryTurn, format_history

# Respuesta exacta que el LLM debe dar cuando los fragmentos no contienen la respuesta. El umbral
# de similitud no alcanza para decidirlo (con actas reales, preguntas con y sin respuesta obtienen
# puntajes que se solapan); con esta marca la API responde "sin información" y sin fuentes.
NO_INFO_MARKER = "SIN_INFORMACION"

RAG_SYSTEM_PROMPT = (
    "Eres un asistente que responde preguntas únicamente con base en los fragmentos de "
    "documentos institucionales que se te entregan a continuación. No uses conocimiento "
    "externo ni inventes información que no esté en esos fragmentos. Responde en español, "
    "de forma clara y concisa, con texto plano o Markdown simple (negritas y listas), sin "
    "fórmulas LaTeX. Si los fragmentos contienen información relacionada con la "
    "pregunta, aunque sea parcial, respóndela con esa información y aclara lo que no esté "
    "cubierto. Solo si ninguno de los fragmentos trata el tema de la pregunta, responde "
    f"únicamente {NO_INFO_MARKER}, sin ningún otro texto."
)

# Modo con razonamiento: misma base (solo los fragmentos, sin conocimiento externo), pero puede
# combinar, comparar, resumir y calcular, y estructura la respuesta en dos partes fijas para que quien
# lee distinga lo que dicen los documentos de lo que se calculó o dedujo.
REASONING_SYSTEM_PROMPT = (
    "Eres un asistente que responde preguntas únicamente con base en los fragmentos de "
    "documentos institucionales que se te entregan a continuación. No uses conocimiento "
    "externo ni inventes información que no esté en esos fragmentos. Responde en español, "
    "con texto plano o Markdown simple (negritas y listas), sin fórmulas LaTeX. "
    "Puedes combinar datos de varios fragmentos, compararlos, contrastarlos, contarlos, "
    "resumirlos y, cuando la pregunta lo pida, calcular con ellos (por ejemplo sumar créditos, "
    "comparar horas, contar acuerdos o resumir lo que dicen varios documentos sobre un tema). "
    "Si los fragmentos contienen información relacionada con la pregunta, aunque sea parcial, "
    "respóndela estructurando la respuesta en estas dos partes, en este orden, con estos títulos "
    "en negrita (no uses encabezados con #): "
    "**Lo que dicen los documentos**: una lista con cada dato que usaste y el nombre del documento "
    "de donde sale. "
    "**Conclusión**: la respuesta a la pregunta, apoyada en esos datos. Si para llegar a ella "
    "combinaste datos, muestra cómo (por ejemplo la operación con sus números, 4 + 4 + 4 = 12, "
    "o la comparación que hiciste); si es una síntesis de lo que dicen los documentos, no inventes "
    "una operación; y si dedujiste algo que no está escrito literalmente, dilo y explica por qué. "
    "Si falta algún dato necesario para responder con certeza, dilo en la conclusión en lugar de "
    "suponerlo. "
    "Solo si ninguno de los fragmentos trata el tema de la pregunta, responde únicamente "
    f"{NO_INFO_MARKER}, sin ningún otro texto."
)


# Cuando la consulta trae historial (feature 014), se agrega a la instrucción de sistema del modo.
HISTORY_INSTRUCTIONS = (
    "Antes del contexto recibirás la conversación anterior, que solo sirve para entender a qué se refiere la pregunta "
    "actual (un pronombre, un seguimiento) y nunca es fuente de datos: no uses nada de ella como hecho, cifra, cálculo ni "
    "cita, aunque una respuesta anterior lo diga. Responde únicamente con los fragmentos del contexto; si la respuesta no "
    "está en ellos, responde como ante cualquier pregunta sin información."
)


# Reescritura de una pregunta de seguimiento (feature 014, estrategia `model`): una llamada corta, sin documentos.
REWRITE_INSTRUCTIONS = (
    "Reescribe la última pregunta como una pregunta completa y autónoma, que se entienda sin la conversación, usando la "
    "conversación anterior solo para saber a qué se refiere (el programa, el tema, el elemento mencionado). No la "
    "respondas ni agregues datos que la conversación no mencione. Si la pregunta ya se entiende sola, devuélvela igual. "
    "Responde solo con la pregunta, en una línea."
)


def build_rewrite_message(question: str, history: list[HistoryTurn]) -> str:
    return f"{format_history(history)}\n\nÚltima pregunta: {question}"


# Prompt propio de cada artefacto: un texto adicional que se anexa a la instrucción del modo. Nunca la reemplaza, así que la
# marca de "sin información" y la regla de responder solo con los fragmentos siguen valiendo.
MAX_CUSTOM_PROMPT_CHARS = 4000

CUSTOM_PROMPT_HEADER = (
    "Instrucciones propias de este artefacto. Complementan las anteriores y no las reemplazan: aunque pidan otra cosa, "
    f"responde siempre solo con los fragmentos del contexto y usa {NO_INFO_MARKER} cuando no traten el tema."
)


def instructions_with_custom_prompt(instructions: str, custom_prompt: str | None) -> str:
    text = (custom_prompt or "").strip()
    return f"{instructions}\n\n{CUSTOM_PROMPT_HEADER}\n{text}" if text else instructions


def instructions_with_history(instructions: str, history: list[HistoryTurn] | None) -> str:
    return f"{instructions}\n\n{HISTORY_INSTRUCTIONS}" if history else instructions


def build_user_message(
    question: str, context_block: str, history: list[HistoryTurn] | None = None
) -> str:
    """El mensaje de usuario, igual para todos los proveedores. Sin historial es el de siempre; con historial, el bloque
    rotulado va antes del contexto y la pregunta queda al final."""
    message = f"Contexto:\n{context_block}\n\nPregunta: {question}"
    block = format_history(history)
    return f"{block}\n\n{message}" if block else message


def is_no_info_answer(answer: str) -> bool:
    return answer.strip().strip(".").upper() == NO_INFO_MARKER


@dataclass
class RagContext:
    domain: str
    document: str
    excerpt: str
    # Número del pasaje dentro de la consulta (de 1 a N). Nulo cuando no se piden citas al modelo:
    # entonces el contexto se formatea como siempre (ver format_context).
    reference: int | None = None


def format_context(context: list["RagContext"]) -> str:
    """Bloque de contexto que se le entrega al modelo, igual para todos los proveedores.

    Sin `reference` la etiqueta es `[Fuente: dominio=..., documento=...]` (el formato de siempre); con
    `reference` lleva el número: `[Fuente 3: dominio=..., documento=...]`.
    """
    return "\n\n".join(
        f"[Fuente{'' if c.reference is None else f' {c.reference}'}: dominio={c.domain}, documento={c.document}]\n{c.excerpt}"
        for c in context
    )


@dataclass
class LLMAnswer:
    """Respuesta del modelo con su uso. Los campos de uso son opcionales: cada proveedor completa los
    que su API informa (OpenRouter informa también el costo real en USD)."""

    text: str
    model: str = ""
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    reasoning_tokens: int | None = None
    cost_usd: float | None = None
    # Por qué terminó la generación, normalizado: "stop" (fin normal), "length" (límite de longitud), "other"
    # (cualquier otro motivo) o None si el proveedor no lo informa (ver normalize_finish_reason).
    finish_reason: str | None = None


def normalize_finish_reason(raw: str | None, kind: str) -> str | None:
    """Motivo de fin de la generación en los tres valores comunes. `kind` es el formato del proveedor:
    "openai" (OpenRouter y GLM: stop, length, content_filter...) o "anthropic" (end_turn, max_tokens...)."""
    if not raw:
        return None
    if kind == "anthropic":
        if raw in ("end_turn", "stop_sequence"):
            return "stop"
        return "length" if raw == "max_tokens" else "other"
    if raw == "stop":
        return "stop"
    return "length" if raw == "length" else "other"


class LLMProvider(ABC):
    @abstractmethod
    def answer(
        self,
        question: str,
        context: list[RagContext],
        instructions: str = RAG_SYSTEM_PROMPT,
        history: list[HistoryTurn] | None = None,
    ) -> LLMAnswer:
        """`instructions` es el mensaje de sistema; cada modo de respuesta trae el suyo. `history` (feature 014) son las
        vueltas anteriores de la conversación: solo sirven para entender la pregunta, nunca son fuente de datos."""
        ...

    def rewrite(self, question: str, history: list[HistoryTurn]) -> LLMAnswer:
        """Reescribe una pregunta de seguimiento como una pregunta completa y autónoma usando la conversación (feature 014).
        No es abstracto: un proveedor que no lo implemente hace que la reformulación caiga a las reglas."""
        raise NotImplementedError("Este proveedor no reescribe preguntas")


@lru_cache
def get_llm_provider(name: str, model: str = "", reasoning_effort: str = "") -> LLMProvider:
    """`model` y `reasoning_effort` los usa el proveedor que admite elegirlos por consulta (OpenRouter);
    los demás tienen un modelo fijo e ignoran estos parámetros."""
    if name == "local":
        from mia.rag.providers.local_llm import LocalLLMProvider

        return LocalLLMProvider()
    if name == "openai":
        from mia.rag.providers.openai_llm import OpenAILLMProvider

        return OpenAILLMProvider()
    if name == "anthropic":
        from mia.rag.providers.anthropic_llm import AnthropicLLMProvider

        return AnthropicLLMProvider()
    if name == "openrouter":
        from mia.rag.providers.openrouter_llm import OpenRouterLLMProvider

        return OpenRouterLLMProvider(model=model, reasoning_effort=reasoning_effort)
    if name == "glm":
        from mia.rag.providers.glm_llm import GLMLLMProvider

        return GLMLLMProvider()
    if name == "gemini":
        from mia.rag.providers.gemini_llm import GeminiLLMProvider

        return GeminiLLMProvider()
    raise ValueError(f"Proveedor de LLM desconocido: {name}")
