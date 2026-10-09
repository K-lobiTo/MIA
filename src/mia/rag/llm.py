from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import lru_cache

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
# combinar, comparar, contar y calcular, y estructura la respuesta en dos partes fijas para que quien
# lee distinga lo que dicen los documentos de lo que se calculó o dedujo.
REASONING_SYSTEM_PROMPT = (
    "Eres un asistente que responde preguntas únicamente con base en los fragmentos de "
    "documentos institucionales que se te entregan a continuación. No uses conocimiento "
    "externo ni inventes información que no esté en esos fragmentos. Responde en español, "
    "con texto plano o Markdown simple (negritas y listas), sin fórmulas LaTeX. "
    "Puedes combinar datos de varios fragmentos, compararlos, contarlos y calcular con ellos "
    "(sumar créditos, comparar horas, contar acuerdos). "
    "Si los fragmentos contienen información relacionada con la pregunta, aunque sea parcial, "
    "respóndela estructurando la respuesta en estas dos partes, en este orden, con estos títulos "
    "en negrita (no uses encabezados con #): "
    "**Lo que dicen los documentos**: una lista con cada dato que usaste y el nombre del documento "
    "de donde sale. "
    "**Cálculo o conclusión**: la operación con sus números (por ejemplo 4 + 4 + 4 = 12) y el "
    "resultado, o lo que se deduce y por qué. "
    "Si falta algún dato necesario para el cálculo, dilo en la segunda parte en lugar de "
    "suponerlo. "
    "Solo si ninguno de los fragmentos trata el tema de la pregunta, responde únicamente "
    f"{NO_INFO_MARKER}, sin ningún otro texto."
)


def is_no_info_answer(answer: str) -> bool:
    return answer.strip().strip(".").upper() == NO_INFO_MARKER


@dataclass
class RagContext:
    domain: str
    document: str
    excerpt: str


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


class LLMProvider(ABC):
    @abstractmethod
    def answer(
        self, question: str, context: list[RagContext], instructions: str = RAG_SYSTEM_PROMPT
    ) -> LLMAnswer:
        """`instructions` es el mensaje de sistema; cada modo de respuesta trae el suyo."""
        ...


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
