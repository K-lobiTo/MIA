from mia.rag.llm import LLMAnswer, LLMProvider, RagContext


class OpenAILLMProvider(LLMProvider):
    def answer(self, question: str, context: list[RagContext]) -> LLMAnswer:
        raise NotImplementedError
