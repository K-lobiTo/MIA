"""Saldo restante en OpenRouter y cuántos días alcanza al ritmo de gasto reciente.

Fuentes (ver specs/002-panel-administracion/research.md, decisión 7):
- GET /api/v1/key con la clave normal de MIA: `limit_remaining`, lo que le queda al límite de crédito
  de esa clave. Es la fuente por defecto: no necesita permisos extra.
- GET /api/v1/credits solo con una clave de gestión (OPENROUTER_MANAGEMENT_KEY, opcional): el saldo de
  toda la cuenta. Esa clave puede crear claves sin límite, por eso no se recomienda en producción.
MIA deja de responder con el menor de los dos valores."""

import logging
from datetime import timedelta

import httpx
from sqlalchemy.orm import Session

from mia.access.caps import day_start_utc
from mia.config import settings
from mia.usage.aggregate import load_rows

logger = logging.getLogger(__name__)

BASE_URL = "https://openrouter.ai/api/v1"
TIMEOUT_SECONDS = 8
WARNING_DAYS = 7
# Fallos esperables al consultar OpenRouter: de red o HTTP, o una respuesta con otro formato.
EXPECTED_ERRORS = (httpx.HTTPError, OSError, KeyError, ValueError, TypeError)


def _fetch_json(url: str, key: str) -> dict:
    response = httpx.get(url, headers={"Authorization": f"Bearer {key}"}, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


def _data(payload: object) -> dict:
    """El objeto `data` de una respuesta de OpenRouter; TypeError si la respuesta tiene otra forma."""
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        raise TypeError("respuesta inesperada de OpenRouter")
    return data


def _unavailable(reason: str) -> dict:
    return {"available": False, "reason": reason}


def _describe(error: Exception) -> str:
    """Motivo legible de un fallo al consultar OpenRouter (sin URLs ni texto técnico de la biblioteca)."""
    if isinstance(error, httpx.HTTPStatusError):
        code = error.response.status_code
        hint = {
            401: "la clave de OpenRouter no es válida",
            403: "la clave no tiene permiso para esta consulta",
            429: "OpenRouter limitó las consultas; reintenta en un momento",
        }.get(code)
        return f"OpenRouter respondió {code}" + (f" ({hint})" if hint else "")
    if isinstance(error, httpx.TimeoutException | TimeoutError):
        return "OpenRouter tardó demasiado en responder"
    if isinstance(error, httpx.HTTPError | OSError):
        return "no se pudo conectar con OpenRouter"
    return "la respuesta de OpenRouter tiene un formato inesperado"


def get_balance(session: Session) -> dict:
    if not settings.openrouter_api_key:
        return _unavailable("No hay una clave de OpenRouter configurada (OPENROUTER_API_KEY) en esta instancia.")

    key_remaining: float | None = None
    try:
        data = _data(_fetch_json(f"{BASE_URL}/key", settings.openrouter_api_key))
        limit_remaining = data.get("limit_remaining")
        key_remaining = float(limit_remaining) if limit_remaining is not None else None
    except EXPECTED_ERRORS as error:
        logger.warning("No se pudo leer el límite de la clave de OpenRouter: %s", error)
        return _unavailable(f"No se pudo consultar OpenRouter: {_describe(error)}.")

    account_remaining: float | None = None
    if settings.openrouter_management_key:
        try:
            data = _data(_fetch_json(f"{BASE_URL}/credits", settings.openrouter_management_key))
            account_remaining = float(data["total_credits"]) - float(data["total_usage"])
        except EXPECTED_ERRORS as error:
            # Si falla solo la lectura de la cuenta, se sigue con el límite de la clave.
            logger.warning("No se pudo leer el saldo de la cuenta de OpenRouter: %s", error)

    known = [v for v in (key_remaining, account_remaining) if v is not None]
    if not known:
        return _unavailable(
            "La clave de OpenRouter no tiene límite de crédito y no hay una clave de gestión configurada "
            "(OPENROUTER_MANAGEMENT_KEY), así que no se puede conocer el saldo."
        )
    remaining = min(known)
    account_limits = account_remaining is not None and (key_remaining is None or account_remaining <= key_remaining)
    source = "account" if account_limits else "key_limit"

    week_start = day_start_utc() - timedelta(days=6)
    week_spend = sum(float(r.cost_usd or 0) for r in load_rows(session, week_start, day_start_utc() + timedelta(days=1), None, None))
    daily = week_spend / 7
    days_left = remaining / daily if daily > 0 else None
    return {
        "available": True,
        "remaining_usd": remaining,
        "source": source,
        "key_limit_remaining_usd": key_remaining,
        "account_remaining_usd": account_remaining,
        "days_left": days_left,
        "avg_daily_spend_usd_7d": daily,
        "warning": days_left is not None and days_left < WARNING_DAYS,
    }
