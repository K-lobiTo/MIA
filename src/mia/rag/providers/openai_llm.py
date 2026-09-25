from mia.rag.llm import LLMProvider, RagContext


class OpenAILLMProvider(LLMProvider):
    def answer(self, question: str, context: list[RagContext]) -> str:
        raise NotImplementedError
