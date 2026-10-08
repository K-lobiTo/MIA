"""Modos de respuesta: cada uno tiene su proveedor, modelo y esfuerzo de razonamiento, definidos por
configuración de la instancia. Los artefactos piden "literal" o "razonamiento" y nunca ven el modelo."""

from dataclasses import dataclass
from decimal import Decimal

from mia.config import settings

LITERAL = "literal"
RAZONAMIENTO = "razonamiento"
MODE_IDS = [LITERAL, RAZONAMIENTO]


@dataclass(frozen=True)
class ModeInfo:
    id: str
    name: str
    description: str


MODES = {
    LITERAL: ModeInfo(LITERAL, "Literal", "Lo que dice exactamente un documento: un acuerdo, un requisito, una fecha."),
    RAZONAMIENTO: ModeInfo(
        RAZONAMIENTO, "Con razonamiento", "Combina, compara y calcula datos de varios documentos."
    ),
}


@dataclass(frozen=True)
class ModeConfig:
    provider: str
    model: str
    reasoning_effort: str
    price_in: float  # USD por millón de tokens, solo para estimar si el proveedor no informa el costo
    price_out: float


def mode_config(mode: str) -> ModeConfig | None:
    """Configuración del modo, o None si la instancia no lo tiene configurado."""
    if mode == LITERAL:
        # Sin variables propias, el modo literal usa la configuración anterior a los modos.
        provider = settings.llm_provider_literal or settings.llm_provider
        model = settings.llm_model_literal or settings.openrouter_model
        effort = settings.llm_reasoning_effort_literal or settings.openrouter_reasoning_effort
        return ModeConfig(provider, model, effort, settings.llm_price_in_literal, settings.llm_price_out_literal)
    if mode == RAZONAMIENTO:
        if not settings.llm_provider_razonamiento:
            return None
        return ModeConfig(
            settings.llm_provider_razonamiento,
            settings.llm_model_razonamiento or settings.openrouter_model,
            settings.llm_reasoning_effort_razonamiento or settings.openrouter_reasoning_effort,
            settings.llm_price_in_razonamiento,
            settings.llm_price_out_razonamiento,
        )
    return None


def mode_available(mode: str) -> tuple[bool, str | None]:
    """Si la instancia puede responder en ese modo y, si no, el motivo para mostrarlo."""
    config = mode_config(mode)
    if config is None or not config.provider:
        return False, "La instancia no tiene configurado un modelo para este modo."
    if config.provider == "openrouter" and not config.model:
        return False, "Falta el modelo de OpenRouter para este modo."
    return True, None


def estimate_cost(mode: str, prompt_tokens: int | None, completion_tokens: int | None) -> Decimal:
    """Costo estimado con los precios de respaldo del modo (0 si no hay precios o tokens)."""
    config = mode_config(mode)
    if config is None:
        return Decimal(0)
    cost = (
        Decimal(str(config.price_in)) * (prompt_tokens or 0) + Decimal(str(config.price_out)) * (completion_tokens or 0)
    ) / Decimal(1_000_000)
    return cost.quantize(Decimal("0.000001"))
