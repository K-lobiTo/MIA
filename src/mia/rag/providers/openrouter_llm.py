from openai import OpenAI

from mia.config import settings
from mia.rag.llm import RAG_SYSTEM_PROMPT, LLMAnswer, LLMProvider, RagContext

# OpenRouter da acceso a muchos modelos (Gemini, GLM, Claude, Qwen...) con una sola cuenta de
# saldo prepagado, y su API es compatible con la de OpenAI.
BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterLLMProvider(LLMProvider):
    def __init__(self, model: str = "", reasoning_effort: str = "") -> None:
        # Cada modo de respuesta puede traer su modelo y esfuerzo; sin ellos rigen OPENROUTER_*.
        self._model = model or settings.openrouter_model
        self._reasoning_effort = reasoning_effort or settings.openrouter_reasoning_effort
        if not self._model:
            raise ValueError("Falta OPENROUTER_MODEL (p. ej. el id del modelo en openrouter.ai/models)")
        # Timeout amplio por intento (un modelo con razonamiento tarda) y pocos reintentos, para que
        # /query responda 502 en vez de quedar colgada.
        self._client = OpenAI(
            api_key=settings.openrouter_api_key or None,
            base_url=BASE_URL,
            timeout=120,
            max_retries=2,
            default_headers={"X-Title": "MIA"},
        )

    def answer(self, question: str, context: list[RagContext]) -> LLMAnswer:
        context_block = "\n\n".join(
            f"[Fuente: dominio={c.domain}, documento={c.document}]\n{c.excerpt}" for c in context
        )
        # Solo proveedores que no guardan los datos para entrenar; con OPENROUTER_ZDR, además, solo
        # los de retención cero. Si ningún proveedor del modelo cumple, OpenRouter responde error en
        # vez de saltarse la restricción.
        extra_body: dict = {
            "provider": {"data_collection": "deny", "zdr": settings.openrouter_zdr}
        }
        if self._reasoning_effort:
            extra_body["reasoning"] = {"effort": self._reasoning_effort}
        completion = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": RAG_SYSTEM_PROMPT},
                {"role": "user", "content": f"Contexto:\n{context_block}\n\nPregunta: {question}"},
            ],
            max_tokens=settings.openrouter_max_tokens,
            extra_body=extra_body,
        )
        return LLMAnswer(
            text=completion.choices[0].message.content or "",
            model=self._model,
            **_usage(getattr(completion, "usage", None)),
        )


def _usage(usage) -> dict:
    """Tokens y costo de la respuesta. OpenRouter incluye `usage.cost` (USD) y el desglose de
    razonamiento siempre, sin pedirlo; `cost` no es un campo estándar del SDK de OpenAI, por eso se
    lee con getattr."""
    if usage is None:
        return {}
    details = getattr(usage, "completion_tokens_details", None)
    cost = getattr(usage, "cost", None)
    return {
        "prompt_tokens": getattr(usage, "prompt_tokens", None),
        "completion_tokens": getattr(usage, "completion_tokens", None),
        "reasoning_tokens": getattr(details, "reasoning_tokens", None) if details else None,
        "cost_usd": float(cost) if cost is not None else None,
    }
