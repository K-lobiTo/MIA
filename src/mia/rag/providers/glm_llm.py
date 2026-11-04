from openai import OpenAI

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

MODEL = "glm-5.3"
# La API de Z.ai es compatible con la de OpenAI: se usa su SDK cambiando la URL base.
BASE_URL = "https://api.z.ai/api/paas/v4/"


class GLMLLMProvider(LLMProvider):
    def __init__(self) -> None:
        # Con razonamiento activado una respuesta puede tardar bastante más que con Gemini:
        # timeout amplio por intento y pocos reintentos, para que /query responda 502 y no se cuelgue.
        self._client = OpenAI(
            api_key=settings.glm_api_key or None, base_url=BASE_URL, timeout=120, max_retries=2
        )

    def answer(
        self,
        question: str,
        context: list[RagContext],
        instructions: str = RAG_SYSTEM_PROMPT,
        history: list[HistoryTurn] | None = None,
    ) -> LLMAnswer:
        context_block = format_context(context)
        completion = self._client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": instructions_with_history(instructions, history)},
                {"role": "user", "content": build_user_message(question, context_block, history)},
            ],
            extra_body={"thinking": {"type": "enabled" if settings.glm_thinking else "disabled"}},
        )
        usage = getattr(completion, "usage", None)
        details = getattr(usage, "completion_tokens_details", None)
        return LLMAnswer(
            text=completion.choices[0].message.content or "",
            model=MODEL,
            finish_reason=normalize_finish_reason(getattr(completion.choices[0], "finish_reason", None), "openai"),
            prompt_tokens=getattr(usage, "prompt_tokens", None),
            completion_tokens=getattr(usage, "completion_tokens", None),
            reasoning_tokens=getattr(details, "reasoning_tokens", None) if details else None,
        )
