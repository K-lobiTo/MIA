from mia.rag.llm import RAG_SYSTEM_PROMPT, LLMAnswer, LLMProvider, RagContext


class OpenAILLMProvider(LLMProvider):
    def answer(
        self, question: str, context: list[RagContext], instructions: str = RAG_SYSTEM_PROMPT
    ) -> LLMAnswer:
        raise NotImplementedError
