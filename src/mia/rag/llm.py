from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import lru_cache


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
