from openai import OpenAI

from mia.config import settings
from mia.rag.llm import RAG_SYSTEM_PROMPT, LLMProvider, RagContext

# OpenRouter da acceso a muchos modelos (Gemini, GLM, Claude, Qwen...) con una sola cuenta de
# saldo prepagado, y su API es compatible con la de OpenAI.
BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterLLMProvider(LLMProvider):
    def __init__(self) -> None:
        if not settings.openrouter_model:
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

    def answer(self, question: str, context: list[RagContext]) -> str:
        context_block = "\n\n".join(
            f"[Fuente: dominio={c.domain}, documento={c.document}]\n{c.excerpt}" for c in context
        )
        # Solo proveedores que no guardan los datos para entrenar; con OPENROUTER_ZDR, además, solo
        # los de retención cero. Si ningún proveedor del modelo cumple, OpenRouter responde error en
        # vez de saltarse la restricción.
        extra_body: dict = {
            "provider": {"data_collection": "deny", "zdr": settings.openrouter_zdr}
        }
        if settings.openrouter_reasoning_effort:
            extra_body["reasoning"] = {"effort": settings.openrouter_reasoning_effort}
        completion = self._client.chat.completions.create(
            model=settings.openrouter_model,
            messages=[
                {"role": "system", "content": RAG_SYSTEM_PROMPT},
                {"role": "user", "content": f"Contexto:\n{context_block}\n\nPregunta: {question}"},
            ],
            extra_body=extra_body,
        )
        return completion.choices[0].message.content or ""
