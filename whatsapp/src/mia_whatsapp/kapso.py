"""Cliente de la API de WhatsApp de Kapso: enviar texto (y, más adelante, imágenes) con un limitador por minuto.

El plan gratuito de Kapso permite 100 solicitudes por minuto: el limitador espera antes de superarlas, así una ráfaga no
pierde respuestas sin necesidad de una cola externa. Un fallo de red o un 5xx se reintenta una sola vez (un mensaje de
más cuesta cuota del plan, que es el límite real) y un 4xx no. Los errores se registran sin teléfonos ni contenido del
mensaje. Ver specs/011-bot-whatsapp-kapso/research.md R9.
"""

import asyncio
import logging
import re
import time
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx

from mia_whatsapp.config import Settings

logger = logging.getLogger("mia_whatsapp")

Destination = tuple[str, str]

RETRY_DELAY_S = 1.0
# Largo máximo del pie de foto de una imagen en WhatsApp.
MAX_IMAGE_CAPTION = 1024
_PHONE_LIKE = re.compile(r"\d{7,}")


@dataclass
class SendResult:
    ok: bool
    status: int | None = None
    # Resumen del error sin teléfonos ni contenido del mensaje; None si se envió.
    error: str | None = None


class RateLimiter:
    """Deja pasar como máximo `per_minute` envíos en cualquier ventana de 60 segundos; los demás esperan."""

    def __init__(
        self,
        per_minute: int,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        self.per_minute = per_minute
        self._clock = clock
        self._sleep = sleep
        self._sent: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            while True:
                now = self._clock()
                while self._sent and self._sent[0] <= now - 60:
                    self._sent.popleft()
                if len(self._sent) < self.per_minute:
                    self._sent.append(now)
                    return
                await self._sleep(max(self._sent[0] + 60 - now, 0.0))


def _summary(response: httpx.Response) -> str:
    """El motivo de un error de Kapso, recortado y sin secuencias de dígitos largas (teléfonos)."""
    try:
        body = response.json()
        error = body.get("error") if isinstance(body, dict) else None
        text = (
            (error.get("message") if isinstance(error, dict) else error)
            or (body.get("message") if isinstance(body, dict) else None)
            or (body.get("detail") if isinstance(body, dict) else None)
            or response.text
        )
    except ValueError:
        text = response.text
    return _PHONE_LIKE.sub("***", str(text))[:200]


class KapsoClient:
    def __init__(
        self,
        settings: Settings,
        client: httpx.AsyncClient | None = None,
        *,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.settings = settings
        self._client = client or httpx.AsyncClient(timeout=15)
        self._sleep = sleep
        self._limiter = RateLimiter(settings.bot_kapso_rate_per_min, clock=clock, sleep=sleep)

    async def aclose(self) -> None:
        await self._client.aclose()

    @staticmethod
    def _with_destination(body: dict, destination: Destination) -> dict:
        kind, value = destination
        if kind == "recipient":
            # Sin teléfono (identificadores de usuario de WhatsApp): se responde al identificador.
            return {**body, "recipient_type": "individual", "recipient": value}
        return {**body, "to": value}

    async def _post(self, number_id: str, body: dict) -> SendResult:
        url = f"{self.settings.kapso_api_url}/{number_id}/messages"
        headers = {"X-API-Key": self.settings.kapso_api_key, "Content-Type": "application/json"}
        last = SendResult(ok=False)
        for attempt in (1, 2):
            await self._limiter.acquire()
            try:
                response = await self._client.post(url, json=body, headers=headers)
            except httpx.HTTPError as exc:
                last = SendResult(ok=False, error=f"{type(exc).__name__}")
                logger.warning("Fallo de red al enviar por Kapso (%s)", type(exc).__name__)
            else:
                if 200 <= response.status_code < 300:
                    return SendResult(ok=True, status=response.status_code)
                last = SendResult(ok=False, status=response.status_code, error=_summary(response))
                logger.warning("Kapso rechazó el envío: %s %s", response.status_code, last.error)
                if response.status_code < 500:
                    return last
            if attempt == 1:
                await self._sleep(RETRY_DELAY_S)
        return last

    async def send_text(self, number_id: str, destination: Destination, text: str) -> SendResult:
        body = self._with_destination({"messaging_product": "whatsapp", "type": "text", "text": {"body": text}}, destination)
        return await self._post(number_id, body)

    async def send_image(self, number_id: str, destination: Destination, link: str, caption: str = "") -> SendResult:
        """Envía una imagen por su enlace público, con su descripción como pie de foto (recortada a 1.024 caracteres)."""
        image: dict = {"link": link}
        if caption.strip():
            image["caption"] = caption.strip()[:MAX_IMAGE_CAPTION]
        body = self._with_destination({"messaging_product": "whatsapp", "type": "image", "image": image}, destination)
        return await self._post(number_id, body)
