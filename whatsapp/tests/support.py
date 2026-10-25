"""Ayudas comunes de las pruebas del servicio: configuración de prueba, firma de avisos, avisos de Kapso de ejemplo y
clientes HTTP simulados con `httpx.MockTransport` (sin red ni Kapso).

La configuración se arma con `make_settings` y no con variables de entorno globales: el `pytest` de la raíz corre
también las pruebas de la API en el mismo proceso, y unas variables puestas aquí (como `BOT_SERVICE_KEY`) le cambiarían
los valores por defecto a su configuración."""

import hashlib
import hmac
import json
from dataclasses import dataclass, field

import httpx

from mia_whatsapp.api_client import MiaApiClient
from mia_whatsapp.config import Settings
from mia_whatsapp.flow import Deps
from mia_whatsapp.kapso import KapsoClient
from mia_whatsapp.state import State
from mia_whatsapp.webhook import IncomingMessage

SECRET = "secreto-del-webhook"
NUMBER_ID = "123456789012345"


def make_settings(**overrides) -> Settings:
    """Configuración de prueba: nunca lee el .env de quien corre las pruebas ni el entorno del proceso."""
    values = {
        "mia_api_url": "https://mia.example.com",
        "bot_service_key": "clave-de-servicio",
        "kapso_api_key": "clave-de-kapso",
        "kapso_webhook_secret": SECRET,
    }
    return Settings(_env_file=None, **{**values, **overrides})


def sign(body: bytes, secret: str = SECRET) -> str:
    """Firma de Kapso: HMAC-SHA256 del cuerpo crudo con el secreto, en hexadecimal minúscula y sin prefijo."""
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def kapso_payload(
    text: str | None = "¿Cuándo es la matrícula?",
    *,
    message_id: str = "wamid.123",
    type: str = "text",
    number_id: str | None = NUMBER_ID,
    phone: str | None = "16315551181",
    user_id: str | None = "US.13491208655302741918",
    conversation_phone: str | None = "16315551181",
    conversation_id: str | None = "conv_123",
) -> dict:
    """Aviso `whatsapp.message.received` de Kapso (sin lote). Cada campo de teléfono o de identificador se puede omitir
    pasando None, porque Kapso avisa que pueden faltar."""
    message: dict = {"id": message_id, "timestamp": "1730092800", "type": type}
    if phone is not None:
        message["from"] = phone
    if user_id is not None:
        message["from_user_id"] = user_id
    if text is not None and type == "text":
        message["text"] = {"body": text}
    conversation: dict = {}
    if conversation_id is not None:
        conversation["id"] = conversation_id
    if conversation_phone is not None:
        conversation["phone_number"] = conversation_phone
    if number_id is not None:
        conversation["phone_number_id"] = number_id
    body: dict = {"message": message, "conversation": conversation, "is_new_conversation": False}
    if number_id is not None:
        body["phone_number_id"] = number_id
    return body


def batch_payload(*items: dict) -> dict:
    """Entrega agrupada de Kapso (buffering): un sobre con `data` y cada elemento con la forma de un aviso."""
    return {"type": "whatsapp.message.received", "batch": True, "data": list(items), "batch_info": {"size": len(items)}}


def webhook_request(payload: dict, *, secret: str = SECRET, event: str = "whatsapp.message.received", key: str = "k1"):
    """Cuerpo crudo y encabezados de un aviso firmado, listos para enviar."""
    body = json.dumps(payload, ensure_ascii=False).encode()
    headers = {
        "content-type": "application/json",
        "x-webhook-event": event,
        "x-webhook-signature": sign(body, secret),
        "x-idempotency-key": key,
    }
    return body, headers


@dataclass
class Recorded:
    """Lo que recibió un servicio simulado: método, ruta, encabezados y cuerpo JSON de cada petición."""

    requests: list[dict] = field(default_factory=list)

    def add(self, request: httpx.Request) -> dict:
        body = json.loads(request.content) if request.content else None
        entry = {
            "method": request.method,
            "path": request.url.path,
            "url": str(request.url),
            "headers": {k.lower(): v for k, v in request.headers.items()},
            "json": body,
        }
        self.requests.append(entry)
        return entry

    def to(self, path_end: str) -> list[dict]:
        return [r for r in self.requests if r["path"].endswith(path_end)]


class FakeMia:
    """API de MIA simulada: responde a `/bot/messages` y `/bot/query` con lo configurado."""

    def __init__(self):
        self.recorded = Recorded()
        self.status = "ok"
        self.month_messages = 1
        self.month_cap = 1800
        self.query_status = 200
        self.query_body: dict = {
            "id": "q1",
            "answer": "La matrícula es del 3 al 7 de agosto.",
            "sources": [{"domain": "Admisión", "document": "horario_matricula.pdf", "excerpt": "..."}],
            "mode": "literal",
            "latency_ms": 1500,
            "no_info": False,
            "images": [],
        }
        self.query_delay = None  # función asíncrona opcional que se espera antes de responder
        self.counts_error: int | None = None

    def transport(self) -> httpx.MockTransport:
        async def handler(request: httpx.Request) -> httpx.Response:
            entry = self.recorded.add(request)
            if request.url.path.endswith("/bot/messages"):
                if self.counts_error is not None:
                    return httpx.Response(self.counts_error, json={"detail": "error"})
                return httpx.Response(
                    200,
                    json={
                        "status": self.status,
                        "month": "2026-10",
                        "month_messages": None if self.status == "unknown_bot" else self.month_messages,
                        "month_cap": None if self.status == "unknown_bot" else self.month_cap,
                    },
                )
            if request.url.path.endswith("/bot/query"):
                if self.query_delay is not None:
                    await self.query_delay(entry)
                return httpx.Response(self.query_status, json=self.query_body if self.query_status == 200 else {"detail": "x"})
            return httpx.Response(404)

        return httpx.MockTransport(handler)


class FakeKapso:
    """API de Kapso simulada: registra cada mensaje enviado y responde con éxito o con el código configurado."""

    def __init__(self):
        self.recorded = Recorded()
        self.status = 200
        self.image_status = 200

    def transport(self) -> httpx.MockTransport:
        def handler(request: httpx.Request) -> httpx.Response:
            entry = self.recorded.add(request)
            kind = (entry["json"] or {}).get("type")
            code = self.image_status if kind == "image" else self.status
            if code >= 400:
                return httpx.Response(code, json={"error": {"message": "falló"}})
            return httpx.Response(200, json={"messages": [{"id": "wamid.out"}]})

        return httpx.MockTransport(handler)

    @property
    def messages(self) -> list[dict]:
        return [r["json"] for r in self.recorded.requests]

    @property
    def texts(self) -> list[str]:
        return [m["text"]["body"] for m in self.messages if m["type"] == "text"]

    @property
    def images(self) -> list[dict]:
        return [m["image"] for m in self.messages if m["type"] == "image"]


class FakeClock:
    """Reloj y espera simulados: dormir adelanta el reloj, sin esperar de verdad."""

    def __init__(self, start: float = 1_000_000.0):
        self.now = start
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    def __call__(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def make_message(**overrides) -> IncomingMessage:
    """Un mensaje de texto ya interpretado, con los valores de un aviso típico."""
    values = {
        "message_id": "wamid.1",
        "idempotency_key": None,
        "number_id": NUMBER_ID,
        "type": "text",
        "text": "¿Cuándo es la matrícula?",
        "person_key": "persona-1",
        "destination": ("to", "16315551181"),
    }
    return IncomingMessage(**{**values, **overrides})


def make_deps(fake_mia: "FakeMia", fake_kapso: "FakeKapso", clock: FakeClock | None = None, **settings) -> Deps:
    """El flujo con la API de MIA y Kapso simulados y un reloj simulado."""
    clock = clock or FakeClock()
    config = make_settings(**settings)
    return Deps(
        settings=config,
        state=State(config, clock=clock),
        api=MiaApiClient(config, httpx.AsyncClient(transport=fake_mia.transport())),
        kapso=KapsoClient(
            config, httpx.AsyncClient(transport=fake_kapso.transport()), sleep=clock.sleep, clock=clock.clock
        ),
        clock=clock.clock,
    )
