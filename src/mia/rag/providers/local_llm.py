from mia.rag.history import HistoryTurn
from mia.rag.llm import RAG_SYSTEM_PROMPT, LLMAnswer, LLMProvider, RagContext


class LocalLLMProvider(LLMProvider):
    """LLM auto-hospedado (p. ej. vía Ollama)."""

    def answer(
        self,
        question: str,
        context: list[RagContext],
        instructions: str = RAG_SYSTEM_PROMPT,
        history: list[HistoryTurn] | None = None,
    ) -> LLMAnswer:
        raise NotImplementedError
