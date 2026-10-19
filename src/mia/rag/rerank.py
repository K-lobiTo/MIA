"""Reranker (feature 009): reordenar y cortar los candidatos de la búsqueda con un modelo que lee juntas la
pregunta y cada fragmento y puntúa cuánto responde uno a la otra.

`RerankProvider` es la interfaz (una implementación local en `mia.rag.providers.local_rerank`); la variable
RERANK_PROVIDER la elige: `none` (por defecto, el comportamiento anterior) o `local`. Un fallo del reranker nunca
rompe una consulta: la ruta cae al orden y al umbral por similitud de vectores.

Ver specs/009-reranker-local/contracts/reranker.md.
"""

import logging
import math
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, replace

from mia.config import settings

logger = logging.getLogger(__name__)


class RerankTimeout(Exception):
    """El tiempo de la consulta para puntuar candidatos se agotó (se comprueba entre lotes)."""


class RerankProvider(ABC):
    @abstractmethod
    def score(self, query: str, passages: list[str], deadline: float | None = None) -> list[float]:
        """Un logit por pasaje, en el mismo orden. `deadline` es un instante de time.perf_counter(): pasado ese
        instante se lanza RerankTimeout. Cualquier otra excepción también es un fallo recuperable para la ruta."""
        ...


def sigmoid(value: float) -> float:
    """Logit a probabilidad entre 0 y 1, sin desbordar con valores grandes en magnitud."""
    if value >= 0:
        return 1.0 / (1.0 + math.exp(-value))
    exp = math.exp(value)
    return exp / (1.0 + exp)


# --- Fábrica ------------------------------------------------------------------------------------

_PROVIDERS: dict[str, RerankProvider] = {}
_FAILED: set[str] = set()
_INVALID_WARNED: set[str] = set()


def reset_rerank_state() -> None:
    """Olvida los proveedores construidos, los fallos recordados y los avisos (para las pruebas)."""
    _PROVIDERS.clear()
    _FAILED.clear()
    _INVALID_WARNED.clear()
    global _last_failure_warning
    _last_failure_warning = None


def get_rerank_provider(name: str) -> RerankProvider | None:
    """El reranker pedido, o None si no hay (none, un nombre inválido o una carga fallida)."""
    normalized = (name or "").strip().lower()
    if normalized in ("", "none"):
        return None
    if normalized != "local":
        if normalized not in _INVALID_WARNED:
            _INVALID_WARNED.add(normalized)
            logger.warning("RERANK_PROVIDER tiene un valor inválido (%r): se trata como none. Usar none o local.", name)
        return None
    if normalized in _PROVIDERS:
        return _PROVIDERS[normalized]
    if normalized in _FAILED:
        return None
    try:
        from mia.rag.providers.local_rerank import LocalRerankProvider

        provider = LocalRerankProvider()
    except Exception:
        # La carga se intenta una vez: reintentarla en cada consulta costaría segundos cada vez.
        logger.exception("No se pudo cargar el reranker local: las consultas usan la similitud de vectores")
        _FAILED.add(normalized)
        return None
    _PROVIDERS[normalized] = provider
    return provider


def rerank_requested(name: str) -> bool:
    """Si la configuración pide el reranker local (aunque el modelo no haya cargado)."""
    return (name or "").strip().lower() == "local"


# --- Selección ----------------------------------------------------------------------------------


@dataclass
class RerankOutcome:
    results: list  # candidatos que siguen, con `score` = puntaje del reranker (0 a 1)
    best: float | None  # mejor puntaje de todos los puntuados, supere o no el mínimo
    scored: int  # cuántos candidatos se puntuaron
    passed: int  # cuántos superaron el mínimo (antes de recortar al límite del modo)
    fell_back: bool = False  # el reranker no estuvo disponible y se usó la similitud
    min_score: float = 0.0


def rerank_candidates(results: list, logits: list[float], min_score: float, limit: int) -> RerankOutcome:
    """Ordena por puntaje de mayor a menor (los empates conservan el orden de entrada, el de coseno), descarta los
    que no llegan a `min_score` y se queda con los primeros `limit`. A cada resultado devuelto le reemplaza `score`
    por la probabilidad (sigmoide del logit) en una copia: los objetos originales no se tocan."""
    if len(results) != len(logits):
        raise ValueError("Debe haber un logit por candidato")
    order = sorted(range(len(results)), key=lambda i: -logits[i])  # estable
    kept = []
    for i in order:
        probability = sigmoid(logits[i])
        if probability >= min_score:
            kept.append(replace(results[i], score=probability))
    return RerankOutcome(
        results=kept[:limit],
        best=sigmoid(max(logits)) if logits else None,
        scored=len(results),
        passed=len(kept),
        min_score=min_score,
    )


def rerank_note(outcome: RerankOutcome) -> str:
    """Nota de Uso (reject_reason) con el puntaje del reranker o la caída a la similitud."""
    if outcome.fell_back:
        return "Reranker no disponible: se usó la similitud"
    best = outcome.best if outcome.best is not None else 0.0
    if outcome.passed > 0:
        return f"Reranker: mejor {best:.3f}, {outcome.passed} de {outcome.scored} sobre el mínimo {outcome.min_score:.2f}"
    return f"Reranker: ninguno sobre el mínimo {outcome.min_score:.2f}, mejor {best:.3f} de {outcome.scored}"


# --- Tiempo, avisos y memoria -------------------------------------------------------------------

_last_failure_warning: float | None = None
_WARNING_INTERVAL_SECONDS = 60.0


def _now() -> float:
    return time.monotonic()


def deadline_for(started: float) -> float | None:
    """Instante límite (de time.perf_counter()) para puntuar, o None si el presupuesto es 0."""
    if settings.rerank_budget_ms <= 0:
        return None
    return started + settings.rerank_budget_ms / 1000


def warn_rerank_failure(exc: Exception) -> None:
    """Aviso de un fallo del reranker en una consulta: como máximo uno por minuto."""
    global _last_failure_warning
    now = _now()
    if _last_failure_warning is None or now - _last_failure_warning >= _WARNING_INTERVAL_SECONDS:
        _last_failure_warning = now
        logger.warning("El reranker falló (%s: %s): la consulta usa la similitud de vectores", type(exc).__name__, exc)


def read_memory_mb() -> tuple[float | None, float | None]:
    """(RSS actual, pico de RSS) del proceso en MB, de /proc/self/status; None si no se puede leer."""
    values: dict[str, float] = {}
    try:
        with open("/proc/self/status", encoding="utf-8") as status:
            for line in status:
                if line.startswith(("VmRSS:", "VmHWM:")):
                    key, rest = line.split(":", 1)
                    values[key] = int(rest.split()[0]) / 1024
    except (OSError, ValueError):
        return None, None
    return values.get("VmRSS"), values.get("VmHWM")


def format_memory(value: float | None) -> str:
    return "?" if value is None else f"{value:.0f}"


def warm_up_rerank_provider() -> None:
    """Carga el reranker al arrancar (si RERANK_PROVIDER=local) y registra la memoria. Nunca lanza: si la carga
    falla, el servicio arranca igual y las consultas usan la similitud."""
    try:
        if (settings.rerank_provider or "").strip().lower() != "local":
            return
        before, _ = read_memory_mb()
        provider = get_rerank_provider(settings.rerank_provider)
        after, peak = read_memory_mb()
        if provider is not None:
            logger.info(
                "Reranker cargado: RSS %s -> %s MB, pico %s MB",
                format_memory(before), format_memory(after), format_memory(peak),
            )
    except Exception:
        logger.exception("Falló la carga del reranker al arrancar")
