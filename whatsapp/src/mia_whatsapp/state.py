"""Estado transitorio del servicio, en memoria y acotado (research R8 de specs/011-bot-whatsapp-kapso).

Mensajes ya vistos (para no responder dos veces un reintento de Kapso) y saludo por persona. Se pierde al reiniciar el
servicio y se acepta en el prototipo; el contador mensual de mensajes, que no debe perderse, vive en la API. Todo tiene
vigencia y un tope de tamaño: una ráfaga de números distintos no agota la memoria (salen primero las entradas más viejas).
La persona se identifica por una clave con hash, nunca por su teléfono.
"""

import asyncio
import time
from collections import OrderedDict, deque
from collections.abc import Callable
from dataclasses import dataclass

from mia_whatsapp.config import Settings

MAX_SEEN = 50_000
MAX_PEOPLE = 50_000

HOUR = 3600
DAY = 24 * HOUR


def _trim(entries: OrderedDict, limit: int) -> None:
    while len(entries) > limit:
        entries.popitem(last=False)


@dataclass
class Allowance:
    """Si un mensaje de una persona se procesa y, si no, si se le avisa (solo la primera vez de cada bloqueo)."""

    allowed: bool
    notify: bool = False


class _Person:
    """Los mensajes aceptados de una persona en el último día y hasta cuándo ya se le avisó del bloqueo."""

    __slots__ = ("accepted", "notified_until")

    def __init__(self) -> None:
        self.accepted: deque[float] = deque()
        self.notified_until = 0.0


class QueryGate:
    """Consultas simultáneas a la API (`concurrent`) y cuántas pueden esperar su turno (`queue_size`): lo que llega con la
    cola llena se descarta sin respuesta, para que una ráfaga de muchos números no sature a MIA ni agote el tope en segundos."""

    def __init__(self, concurrent: int, queue_size: int):
        self._semaphore = asyncio.Semaphore(concurrent)
        self._queue_size = queue_size
        self._waiting = 0

    async def enter(self) -> bool:
        """Toma un lugar para consultar, esperando si hace falta; falso si la cola está llena (hay que descartar)."""
        if self._semaphore.locked():
            if self._waiting >= self._queue_size:
                return False
            self._waiting += 1
            try:
                await self._semaphore.acquire()
            finally:
                self._waiting -= 1
        else:
            await self._semaphore.acquire()
        return True

    def leave(self) -> None:
        self._semaphore.release()


class State:
    def __init__(self, settings: Settings, clock: Callable[[], float] = time.time):
        self.settings = settings
        self._clock = clock
        self._seen: OrderedDict[str, float] = OrderedDict()
        self._greeted: OrderedDict[str, float] = OrderedDict()
        self._people: OrderedDict[str, _Person] = OrderedDict()
        self.gate = QueryGate(settings.bot_max_concurrent_queries, settings.bot_queue_size)

    # --- Mensajes vistos ---

    @property
    def seen_count(self) -> int:
        return len(self._seen)

    def seen(self, key: str) -> bool:
        """Si el id ya se vio dentro de su vigencia; si no, lo registra y devuelve falso."""
        now = self._clock()
        ttl = self.settings.bot_seen_ttl_hours * 3600
        previous = self._seen.get(key)
        if previous is not None and now - previous < ttl:
            return True
        self._seen.pop(key, None)
        self._seen[key] = now
        _trim(self._seen, MAX_SEEN)
        return False

    # --- Saludo ---

    @property
    def greeted_count(self) -> int:
        return len(self._greeted)

    def needs_greeting(self, person: str | None) -> bool:
        """Se saluda en la primera respuesta a una persona y de nuevo pasadas `bot_greeting_hours` horas."""
        if person is None:
            return True
        last = self._greeted.get(person)
        return last is None or self._clock() - last >= self.settings.bot_greeting_hours * 3600

    def mark_greeted(self, person: str | None) -> None:
        if person is None:
            return
        self._greeted.pop(person, None)
        self._greeted[person] = self._clock()
        _trim(self._greeted, MAX_PEOPLE)

    # --- Límite por persona ---

    @property
    def people_count(self) -> int:
        return len(self._people)

    def allow(self, person: str | None) -> Allowance:
        """Ventanas deslizantes por persona: `bot_max_messages_per_hour` en la última hora y `bot_max_messages_per_day` en
        el último día. Pasado el límite el mensaje no se procesa, y solo el primero de cada bloqueo trae `notify`. Los
        mensajes bloqueados NO suman a la ventana: el bloqueo termina cuando pasa la ventana y no se alarga por insistir."""
        if person is None:
            return Allowance(True)  # sin identificador no hay a quién limitar
        now = self._clock()
        entry = self._people.pop(person, None) or _Person()
        self._people[person] = entry
        _trim(self._people, MAX_PEOPLE)
        while entry.accepted and entry.accepted[0] <= now - DAY:
            entry.accepted.popleft()
        in_hour = [t for t in entry.accepted if t > now - HOUR]
        hourly, daily = self.settings.bot_max_messages_per_hour, self.settings.bot_max_messages_per_day
        blocked_until = 0.0
        if len(in_hour) >= hourly:
            blocked_until = max(blocked_until, in_hour[len(in_hour) - hourly] + HOUR)
        if len(entry.accepted) >= daily:
            blocked_until = max(blocked_until, entry.accepted[len(entry.accepted) - daily] + DAY)
        if blocked_until > 0:
            notify = now >= entry.notified_until
            if notify:
                entry.notified_until = blocked_until
            return Allowance(False, notify)
        entry.accepted.append(now)
        return Allowance(True)

    # --- Limpieza ---

    def cleanup(self) -> None:
        """Retira lo vencido. Las entradas están en orden de llegada, así que se corta en la primera vigente."""
        now = self._clock()
        seen_ttl = self.settings.bot_seen_ttl_hours * 3600
        while self._seen and now - next(iter(self._seen.values())) >= seen_ttl:
            self._seen.popitem(last=False)
        greeting_ttl = self.settings.bot_greeting_hours * 3600
        while self._greeted and now - next(iter(self._greeted.values())) >= greeting_ttl:
            self._greeted.popitem(last=False)
        for key, entry in list(self._people.items()):
            while entry.accepted and entry.accepted[0] <= now - DAY:
                entry.accepted.popleft()
            if not entry.accepted and entry.notified_until <= now:
                del self._people[key]
