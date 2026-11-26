"""Lectura periódica del almacén vectorial para que no se considere inactivo.

Qdrant Cloud suspende un clúster gratuito tras una semana sin actividad y lo elimina tras cuatro. Con poco uso
(vacaciones, entre períodos) eso dejaría a MIA sin responder. La API hace al arrancar, y luego cada
`QDRANT_KEEPALIVE_HOURS`, una búsqueda mínima: no usa modelos, no cuesta nada y no cambia datos. Solo protege
mientras la API esté encendida.
"""

import asyncio
import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)

# Tras un fallo se reintenta antes, sin esperar el intervalo completo.
RETRY_SECONDS = 3600


async def keep_active(ping: Callable[[], None], interval_seconds: float, retry_seconds: float = RETRY_SECONDS) -> None:
    """Llama a `ping` ahora y cada `interval_seconds`, hasta que se cancele la tarea. Un fallo solo deja un aviso.
    Si el almacén no sabe hacer la lectura (`NotImplementedError`), termina."""
    while True:
        try:
            await asyncio.to_thread(ping)
        except NotImplementedError:
            return
        except Exception as exc:  # noqa: BLE001 (nunca debe tumbar la API)
            logger.warning("Lectura de mantenimiento de Qdrant fallida (%s: %s)", type(exc).__name__, exc)
            await asyncio.sleep(min(retry_seconds, interval_seconds))
        else:
            logger.info("Lectura de mantenimiento de Qdrant hecha")
            await asyncio.sleep(interval_seconds)
