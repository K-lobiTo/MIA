from google import genai
from google.genai import types

from mia.config import settings
from mia.rag.llm import RAG_SYSTEM_PROMPT, LLMAnswer, LLMProvider, RagContext

MODEL = "gemini-3.5-flash-lite"

# Con el modelo saturado (503 "high demand", frecuente en el tier gratuito) el SDK reintenta sin
# límite práctico y la consulta queda colgada. Se acota: pocos reintentos y un timeout por
# intento, para que /query responda 502 en vez de no responder.
HTTP_OPTIONS = types.HttpOptions(
    timeout=30_000,  # milisegundos
    retry_options=types.HttpRetryOptions(attempts=3, initial_delay=2, max_delay=10),
)


class GeminiLLMProvider(LLMProvider):
    def __init__(self) -> None:
        self._client = genai.Client(
            api_key=settings.gemini_api_key or None, http_options=HTTP_OPTIONS
        )

    def answer(
        self, question: str, context: list[RagContext], instructions: str = RAG_SYSTEM_PROMPT
    ) -> LLMAnswer:
        context_block = "\n\n".join(
            f"[Fuente: dominio={c.domain}, documento={c.document}]\n{c.excerpt}" for c in context
        )
        interaction = self._client.interactions.create(
            model=MODEL,
            system_instruction=instructions,
            input=f"Contexto:\n{context_block}\n\nPregunta: {question}",
        )
        usage = getattr(interaction, "usage", None)
        return LLMAnswer(
            text=interaction.output_text,
            model=MODEL,
            prompt_tokens=getattr(usage, "total_input_tokens", None),
            completion_tokens=getattr(usage, "total_output_tokens", None),
            reasoning_tokens=getattr(usage, "total_thought_tokens", None),
        )
