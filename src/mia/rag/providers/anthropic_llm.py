import anthropic

from mia.config import settings
from mia.rag.history import HistoryTurn
from mia.rag.llm import (
    RAG_SYSTEM_PROMPT,
    LLMAnswer,
    LLMProvider,
    RagContext,
    build_user_message,
    format_context,
    instructions_with_history,
    normalize_finish_reason,
)

MODEL = "claude-sonnet-5"


class AnthropicLLMProvider(LLMProvider):
    def __init__(self) -> None:
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key or None)

    def answer(
        self,
        question: str,
        context: list[RagContext],
        instructions: str = RAG_SYSTEM_PROMPT,
        history: list[HistoryTurn] | None = None,
    ) -> LLMAnswer:
        context_block = format_context(context)
        message = self._client.messages.create(
            model=MODEL,
            max_tokens=16000,
            system=instructions_with_history(instructions, history),
            output_config={"effort": settings.anthropic_effort},
            messages=[
                {"role": "user", "content": build_user_message(question, context_block, history)}
            ],
        )
        usage = getattr(message, "usage", None)
        return LLMAnswer(
            text=next((block.text for block in message.content if block.type == "text"), ""),
            model=MODEL,
            finish_reason=normalize_finish_reason(getattr(message, "stop_reason", None), "anthropic"),
            prompt_tokens=getattr(usage, "input_tokens", None),
            completion_tokens=getattr(usage, "output_tokens", None),
        )
