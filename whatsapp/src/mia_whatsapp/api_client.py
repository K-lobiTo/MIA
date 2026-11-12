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


@dataclass(frozen=True)
class ContactState:
    """El estado del contacto de una persona (feature 017): nunca su nombre ni su correo, solo si existen."""

    # pendiente, invitada, entrego o declino.
    status: str
    email_retried: bool
    has_name: bool
    has_email: bool


def _contact_state(value) -> "ContactState | None":
    """El estado de contacto de la respuesta de la API; una forma rara (o su ausencia) es None."""
    if not isinstance(value, dict):
        return None
    status = value.get("status")
    flags = (value.get("email_retried"), value.get("has_name"), value.get("has_email"))
    if status not in ("pendiente", "invitada", "entrego", "declino") or not all(isinstance(f, bool) for f in flags):
        return None
    return ContactState(status=status, email_retried=flags[0], has_name=flags[1], has_email=flags[2])


@dataclass
class ContactResult:
    """El resultado de un evento de contacto. Nunca lanza: cualquier falla es `ok=False`."""

    ok: bool
    claimed: bool = False
    had_data: bool = False
    state: ContactState | None = None
    # La API respondió 409: el evento no aplica al estado actual (no es una falla, no se insiste).
    conflict: bool = False


@dataclass
class CountResult:
    # ok, disabled, cap_reached, unknown_bot, o error (la API falló o no se pudo llamar).
    status: str
    month_messages: int | None = None
    month_cap: int | None = None
    # Las vueltas (pregunta y respuesta) que recuerda el bot, de 1 a 10 (feature 014); vacío si la API no lo informa.
    context_turns: int | None = None
    # El contacto de la persona (feature 017); solo si se envió el teléfono y la API lo informó.
    contact: ContactState | None = None


def _context_turns(body: dict) -> int | None:
    """La memoria del bot de la respuesta de la API; una forma rara (no entero, fuera de 1 a 10) se ignora."""
    value = body.get("context_turns")
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 10:
        return None
    return value


@dataclass
class QueryResult:
    # answer, no_info, clarify (la pregunta es ambigua entre programas, feature 013), unknown_bot, o unavailable (403, 429,
    # 5xx, tiempo agotado, error de red o respuesta inválida).
    kind: str
    answer: str = ""
    sources: list[str] = field(default_factory=list)
    images: list[ImageRef] = field(default_factory=list)
    status_code: int | None = None
    # En `clarify`, los programas candidatos; en `answer`, los programas de los documentos citados.
    candidates: list[str] = field(default_factory=list)
    programs: list[str] = field(default_factory=list)


def _names(value) -> list[str]:
    """Una lista de nombres de programa de la respuesta; todo lo que no sea texto no vacío se ignora."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


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

    async def count_messages(
        self, number_id: str, received: int = 0, sent: int = 0, phone: str | None = None
    ) -> CountResult:
        """Suma mensajes al mes del bot y devuelve su estado. Cualquier falla es el estado `error`. El teléfono (feature 017)
        va solo si se pasa (con `BOT_CONTACT=on`); sin él la llamada es exactamente la de antes."""
        payload: dict = {"number_id": number_id, "received": received, "sent": sent}
        if phone is not None:
            payload["phone"] = phone
        try:
            response = await self._client.post(
                f"{self.settings.mia_api_url}/bot/messages",
                json=payload,
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
                status=str(body["status"]),
                month_messages=body.get("month_messages"),
                month_cap=body.get("month_cap"),
                context_turns=_context_turns(body),
                contact=_contact_state(body.get("contact")),
            )
        except (ValueError, KeyError, TypeError, AttributeError):
            logger.warning("La API respondió algo inesperado al contar mensajes")
            return CountResult(status="error")

    async def put_contact(
        self, number_id: str, phone: str, event: str, name: str | None = None, email: str | None = None
    ) -> ContactResult:
        """Aplica un evento al contacto de una persona (`PUT /bot/contacts`). NUNCA lanza ni registra el teléfono, el nombre ni
        el correo: un error de red, un tiempo agotado, 401, 404, 422 o una respuesta rara es `ok=False` (el flujo sigue como
        sin la función); 409 es `conflict=True` (el evento no aplica al estado actual)."""
        payload: dict = {"number_id": number_id, "phone": phone, "event": event}
        if name is not None:
            payload["name"] = name
        if email is not None:
            payload["email"] = email
        try:
            response = await self._client.put(
                f"{self.settings.mia_api_url}/bot/contacts", json=payload, headers=self._headers(), timeout=COUNT_TIMEOUT_S
            )
        except httpx.HTTPError as exc:
            logger.warning("No se pudo guardar el contacto en la API (%s)", type(exc).__name__)
            return ContactResult(ok=False)
        if response.status_code == 409:
            return ContactResult(ok=False, conflict=True)
        if response.status_code == 401:
            self._credential_rejected()
        if response.status_code != 200:
            logger.warning("La API respondió %s al guardar el contacto", response.status_code)
            return ContactResult(ok=False)
        try:
            body = response.json()
            state = _contact_state(body.get("contact"))
            if state is None:
                raise ValueError
            return ContactResult(
                ok=True, claimed=bool(body.get("claimed")), had_data=bool(body.get("had_data")), state=state
            )
        except (ValueError, TypeError, AttributeError):
            logger.warning("La API respondió algo inesperado al guardar el contacto")
            return ContactResult(ok=False)

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
            candidates = _names(body.get("clarify"))
            programs = _names(body.get("programs"))
        except (ValueError, KeyError, TypeError, AttributeError):
            logger.warning("La API respondió algo inesperado a la consulta")
            return QueryResult(kind="unavailable", status_code=status)
        if no_info:
            kind = "clarify" if candidates else "no_info"
            return QueryResult(kind=kind, candidates=candidates, status_code=status)
        return QueryResult(
            kind="answer", answer=answer, sources=sources, images=images, status_code=status, programs=programs
        )
