import anthropic

from mia.config import settings
from mia.rag.llm import RAG_SYSTEM_PROMPT, LLMAnswer, LLMProvider, RagContext

MODEL = "claude-sonnet-5"


class AnthropicLLMProvider(LLMProvider):
    def __init__(self) -> None:
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key or None)

    def answer(
        self, question: str, context: list[RagContext], instructions: str = RAG_SYSTEM_PROMPT
    ) -> LLMAnswer:
        context_block = "\n\n".join(
            f"[Fuente: dominio={c.domain}, documento={c.document}]\n{c.excerpt}" for c in context
        )
        message = self._client.messages.create(
            model=MODEL,
            max_tokens=16000,
            system=instructions,
            output_config={"effort": settings.anthropic_effort},
            messages=[{"role": "user", "content": f"Contexto:\n{context_block}\n\nPregunta: {question}"}],
        )
        usage = getattr(message, "usage", None)
        return LLMAnswer(
            text=next((block.text for block in message.content if block.type == "text"), ""),
            model=MODEL,
            prompt_tokens=getattr(usage, "input_tokens", None),
            completion_tokens=getattr(usage, "output_tokens", None),
        )
