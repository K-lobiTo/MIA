"""Lista de equivalencias de siglas (feature 010): lectura de la tabla `sigla_equivalences` con una caché en
proceso de HYBRID_EQUIVALENCES_TTL_SECONDS, para que una sigla de la pregunta busque también su forma
desarrollada y al revés.

Ver specs/010-busqueda-hibrida/contracts/equivalencias-api.md.
"""

import threading
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from mia.config import settings
from mia.rag.lexical import Equivalence
from mia.storage.models import SiglaEquivalence

_lock = threading.Lock()
_cache: tuple[float, list[Equivalence]] | None = None


def _now() -> float:
    return time.monotonic()


def invalidate_equivalences() -> None:
    """Vacía la caché: lo llama cada escritura de la lista y las pruebas."""
    global _cache
    with _lock:
        _cache = None


def get_equivalences(session: Session) -> list[Equivalence]:
    """La lista de equivalencias normalizada. Dentro de `hybrid_equivalences_ttl_seconds` no vuelve a consultar la
    base; con 0 siempre la consulta."""
    global _cache
    ttl = settings.hybrid_equivalences_ttl_seconds
    now = _now()
    with _lock:
        if ttl > 0 and _cache is not None and now - _cache[0] < ttl:
            return list(_cache[1])
    rows = session.scalars(select(SiglaEquivalence).order_by(SiglaEquivalence.sigla, SiglaEquivalence.form))
    equivalences = [Equivalence(sigla=row.sigla, form=row.form) for row in rows]
    if ttl > 0:
        with _lock:
            _cache = (now, equivalences)
    return list(equivalences)
