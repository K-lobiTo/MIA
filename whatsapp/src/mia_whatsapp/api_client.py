"""Cliente de la API de MIA para el servicio del bot: contar mensajes y consultar con el artefacto asignado.

Habla con `POST /bot/messages` y `POST /bot/query` con la credencial de servicio (`X-Bot-Service-Key`). Ningún error de
la API o de red se propaga: se traduce a un resultado que el flujo sabe tratar. Contrato en
specs/011-bot-whatsapp-kapso/contracts/bot-servicio-api.md.
"""

import logging
from dataclasses import dataclass, field

import httpx

from mia_whatsapp.config import Settings

logger = logging.getLogger("mia_whatsapp")

# La cuenta de mensajes es una llamada rápida: no debe esperar como una consulta al modelo.
COUNT_TIMEOUT_S = 10


@dataclass(frozen=True)
class ImageRef:
    # Ruta relativa `/media/{public_id}` de la API; el servicio la completa con MIA_API_URL.
    url: str
    caption: str
    document: str


@dataclass
class CountResult:
    # ok, disabled, cap_reached, unknown_bot, o error (la API falló o no se pudo llamar).
    status: str
    month_messages: int | None = None
    month_cap: int | None = None


@dataclass
class QueryResult:
    # answer, no_info, unknown_bot, o unavailable (403, 429, 5xx, tiempo agotado, error de red o respuesta inválida).
    kind: str
    answer: str = ""
    sources: list[str] = field(default_factory=list)
    images: list[ImageRef] = field(default_factory=list)
    status_code: int | None = None


class MiaApiClient:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self.settings = settings
        self._client = client or httpx.AsyncClient()

    async def aclose(self) -> None:
        await self._client.aclose()

    def _headers(self) -> dict[str, str]:
        return {"X-Bot-Service-Key": self.settings.bot_service_key}

    def _credential_rejected(self) -> None:
        logger.error("La API rechazó la credencial de servicio: revisar que BOT_SERVICE_KEY sea la misma en la API y aquí")

    async def count_messages(self, number_id: str, received: int = 0, sent: int = 0) -> CountResult:
        """Suma mensajes al mes del bot y devuelve su estado. Cualquier falla es el estado `error`."""
        try:
            response = await self._client.post(
                f"{self.settings.mia_api_url}/bot/messages",
                json={"number_id": number_id, "received": received, "sent": sent},
                headers=self._headers(),
                timeout=COUNT_TIMEOUT_S,
            )
        except httpx.HTTPError as exc:
            logger.warning("No se pudo contar el mensaje en la API (%s)", type(exc).__name__)
            return CountResult(status="error")
        if response.status_code == 401:
            self._credential_rejected()
        if response.status_code != 200:
            logger.warning("La API respondió %s al contar mensajes", response.status_code)
            return CountResult(status="error")
        try:
            body = response.json()
            return CountResult(
                status=str(body["status"]), month_messages=body.get("month_messages"), month_cap=body.get("month_cap")
            )
        except (ValueError, KeyError, TypeError, AttributeError):
            logger.warning("La API respondió algo inesperado al contar mensajes")
            return CountResult(status="error")

    async def query(self, number_id: str, question: str) -> QueryResult:
        """Consulta con el artefacto del bot (siempre en modo literal, lo fija la API)."""
        timeout = self.settings.bot_query_timeout_s
        try:
            response = await self._client.post(
                f"{self.settings.mia_api_url}/bot/query",
                json={"number_id": number_id, "question": question},
                headers=self._headers(),
                timeout=timeout,
            )
        except httpx.HTTPError as exc:
            logger.warning("No se pudo consultar a la API (%s)", type(exc).__name__)
            return QueryResult(kind="unavailable")
        status = response.status_code
        if status == 404:
            return QueryResult(kind="unknown_bot", status_code=status)
        if status == 401:
            self._credential_rejected()
        if status != 200:
            logger.info("La API respondió %s a la consulta", status)
            return QueryResult(kind="unavailable", status_code=status)
        try:
            body = response.json()
            answer = str(body["answer"])
            sources = [str(s["document"]) for s in body.get("sources") or []]
            images = [
                ImageRef(url=str(i["url"]), caption=str(i.get("caption") or ""), document=str(i.get("document") or ""))
                for i in body.get("images") or []
            ]
            no_info = bool(body.get("no_info", False))
        except (ValueError, KeyError, TypeError, AttributeError):
            logger.warning("La API respondió algo inesperado a la consulta")
            return QueryResult(kind="unavailable", status_code=status)
        if no_info:
            return QueryResult(kind="no_info", status_code=status)
        return QueryResult(kind="answer", answer=answer, sources=sources, images=images, status_code=status)
