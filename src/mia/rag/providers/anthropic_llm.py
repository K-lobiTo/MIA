import anthropic

from mia.config import settings
from mia.rag.llm import RAG_SYSTEM_PROMPT, LLMProvider, RagContext

MODEL = "claude-sonnet-5"


class AnthropicLLMProvider(LLMProvider):
    def __init__(self) -> None:
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key or None)

    def answer(self, question: str, context: list[RagContext]) -> str:
        context_block = "\n\n".join(
            f"[Fuente: dominio={c.domain}, documento={c.document}]\n{c.excerpt}" for c in context
        )
        message = self._client.messages.create(
            model=MODEL,
            max_tokens=16000,
            system=RAG_SYSTEM_PROMPT,
            output_config={"effort": settings.anthropic_effort},
            messages=[{"role": "user", "content": f"Contexto:\n{context_block}\n\nPregunta: {question}"}],
        )
        return next((block.text for block in message.content if block.type == "text"), "")
