from mia.rag.llm import RAG_SYSTEM_PROMPT, LLMAnswer, LLMProvider, RagContext


class LocalLLMProvider(LLMProvider):
    """LLM auto-hospedado (p. ej. vía Ollama)."""

    def answer(
        self, question: str, context: list[RagContext], instructions: str = RAG_SYSTEM_PROMPT
    ) -> LLMAnswer:
        raise NotImplementedError
