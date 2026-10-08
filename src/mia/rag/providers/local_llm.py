from mia.rag.llm import LLMAnswer, LLMProvider, RagContext


class LocalLLMProvider(LLMProvider):
    """LLM auto-hospedado (p. ej. vía Ollama)."""

    def answer(self, question: str, context: list[RagContext]) -> LLMAnswer:
        raise NotImplementedError
