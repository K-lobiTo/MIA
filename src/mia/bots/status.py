"""Estado de un bot de WhatsApp (feature 011): si hoy puede responder y por qué no, y qué dominios ve.

Se calcula en cada consulta a partir de la base, sin guardar nada: un cambio de artefacto, de accesos o de estado rige
desde el mensaje siguiente (BOT-3, BOT-4 y SC-006 de la spec).
"""

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from mia.access.permissions import configured_domain_ids
from mia.bots.usage import MonthUsage, cap_reached, current_month, month_usage
from mia.config import settings
from mia.storage.models import Artifact, Bot, Domain, Unit

Status = Literal["ok", "disabled", "cap_reached"]

REASON_BOT_DISABLED = "El bot está desactivado."
REASON_NO_ARTIFACT = "No tiene artefacto asignado."
REASON_ARTIFACT_DISABLED = "El artefacto asignado está desactivado."
REASON_CAP_REACHED = "Se alcanzó el tope mensual de mensajes."


@dataclass
class BotState:
    status: Status
    reason: str | None
    usage: MonthUsage
    cap: int
    month: str
    artifact: Artifact | None

    @property
    def available(self) -> bool:
        return self.status == "ok"


def find_bot_by_number(session: Session, number_id: str) -> Bot | None:
    """El bot que responde al número de Kapso dado (su `phone_number_id`), o None."""
    return session.scalar(select(Bot).where(Bot.kapso_number_id == number_id))


def bot_state(session: Session, bot: Bot, month: str | None = None) -> BotState:
    """Si el bot puede responder hoy. `cap_reached` gana sobre `disabled` cuando coinciden: con el tope alcanzado el
    bot no envía ni un mensaje más, ni siquiera el aviso de "no disponible"."""
    month = month or current_month()
    usage = month_usage(session, bot.id, month)
    cap = settings.bot_monthly_message_cap
    artifact = session.get(Artifact, bot.artifact_id) if bot.artifact_id else None
    if cap_reached(usage.total, cap):
        status, reason = "cap_reached", REASON_CAP_REACHED
    elif not bot.active:
        status, reason = "disabled", REASON_BOT_DISABLED
    elif artifact is None:
        status, reason = "disabled", REASON_NO_ARTIFACT
    elif not artifact.active:
        status, reason = "disabled", REASON_ARTIFACT_DISABLED
    else:
        status, reason = "ok", None
    return BotState(status=status, reason=reason, usage=usage, cap=cap, month=month, artifact=artifact)


def domain_labels(session: Session, artifact: Artifact | None) -> list[str]:
    """Etiquetas `Programa / Dominio` de los dominios que el artefacto cubre hoy, ordenadas; solo el nombre si el
    dominio no tiene programa; vacía sin artefacto. Dos consultas, no una por dominio."""
    if artifact is None:
        return []
    domain_ids = configured_domain_ids(session, artifact)
    if not domain_ids:
        return []
    domains = list(session.scalars(select(Domain).where(Domain.id.in_(domain_ids))))
    units = {u.id: u.name for u in session.scalars(select(Unit))}
    labels = []
    for domain in domains:
        unit = units.get(domain.unit_id or "")
        labels.append(f"{unit} / {domain.name}" if unit else domain.name)
    return sorted(labels, key=str.lower)
