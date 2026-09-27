from google import genai

from mia.config import settings
from mia.rag.llm import LLMProvider, RagContext

MODEL = "gemini-3.5-flash-lite"

SYSTEM_PROMPT = (
    "Eres un asistente que responde preguntas únicamente con base en los fragmentos de "
    "documentos institucionales que se te entregan a continuación. No uses conocimiento "
    "externo ni inventes información que no esté en esos fragmentos. Responde en español, "
    "de forma clara y concisa."
)


class GeminiLLMProvider(LLMProvider):
    def __init__(self) -> None:
        self._client = (
            genai.Client(api_key=settings.gemini_api_key) if settings.gemini_api_key else genai.Client()
        )

    def answer(self, question: str, context: list[RagContext]) -> str:
        context_block = "\n\n".join(
            f"[Fuente: dominio={c.domain}, documento={c.document}]\n{c.excerpt}" for c in context
        )
        interaction = self._client.interactions.create(
            model=MODEL,
            system_instruction=SYSTEM_PROMPT,
            input=f"Contexto:\n{context_block}\n\nPregunta: {question}",
        )
        return interaction.output_text
