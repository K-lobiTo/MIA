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
    "de forma clara y concisa. Si los fragmentos contienen información relacionada con la "
    "pregunta, aunque sea parcial, respóndela con esa información y aclara lo que no esté "
    "cubierto. Solo si ninguno de los fragmentos trata el tema de la pregunta, responde "
    f"únicamente {NO_INFO_MARKER}, sin ningún otro texto."
)


def is_no_info_answer(answer: str) -> bool:
    return answer.strip().strip(".").upper() == NO_INFO_MARKER


@dataclass
class RagContext:
    domain: str
    document: str
    excerpt: str


class LLMProvider(ABC):
    @abstractmethod
    def answer(self, question: str, context: list[RagContext]) -> str: ...


@lru_cache
def get_llm_provider(name: str) -> LLMProvider:
    if name == "local":
        from mia.rag.providers.local_llm import LocalLLMProvider

        return LocalLLMProvider()
    if name == "openai":
        from mia.rag.providers.openai_llm import OpenAILLMProvider

        return OpenAILLMProvider()
    if name == "anthropic":
        from mia.rag.providers.anthropic_llm import AnthropicLLMProvider

        return AnthropicLLMProvider()
    if name == "gemini":
        from mia.rag.providers.gemini_llm import GeminiLLMProvider

        return GeminiLLMProvider()
    raise ValueError(f"Proveedor de LLM desconocido: {name}")
