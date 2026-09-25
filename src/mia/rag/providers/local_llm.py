from mia.rag.llm import LLMProvider, RagContext


class LocalLLMProvider(LLMProvider):
    """LLM auto-hospedado (p. ej. vía Ollama)."""

    def answer(self, question: str, context: list[RagContext]) -> str:
        raise NotImplementedError
