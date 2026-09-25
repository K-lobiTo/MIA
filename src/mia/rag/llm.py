from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class RagContext:
    domain: str
    document: str
    excerpt: str


class LLMProvider(ABC):
    @abstractmethod
    def answer(self, question: str, context: list[RagContext]) -> str: ...


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
    raise ValueError(f"Proveedor de LLM desconocido: {name}")
