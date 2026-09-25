from mia.rag.llm import LLMProvider, RagContext


class AnthropicLLMProvider(LLMProvider):
    def answer(self, question: str, context: list[RagContext]) -> str:
        raise NotImplementedError
