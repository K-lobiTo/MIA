"""Límite de intentos fallidos de inicio de sesión (feature 015, research R3 y R4).

Contadores en memoria del proceso, acotados (como el estado del bot): fallos recientes por usuario y por origen. Con
`login_max_attempts` fallos en la ventana de bloqueo el usuario queda bloqueado hasta que el más antiguo de esos fallos salga
de la ventana, **aunque la contraseña sea correcta**; el origen tiene su propio tope. Al reiniciar la API se pierden: el
límite por usuario es el que protege de verdad."""

import math
import time
from collections import OrderedDict, deque
from collections.abc import Callable

from mia.config import settings

MAX_ENTRIES = 10_000


class LoginThrottle:
    def __init__(self, clock: Callable[[], float] = time.monotonic, max_entries: int = MAX_ENTRIES):
        self._clock = clock
        self._max = max_entries
        self._users: OrderedDict[str, deque[float]] = OrderedDict()
        self._origins: OrderedDict[str, deque[float]] = OrderedDict()

    @property
    def size(self) -> int:
        return len(self._users) + len(self._origins)

    def _window(self) -> float:
        return settings.login_lock_minutes * 60

    def _recent(self, table: OrderedDict, key: str) -> deque[float]:
        fails = table.get(key)
        if fails is None:
            return deque()
        horizon = self._clock() - self._window()
        while fails and fails[0] <= horizon:
            fails.popleft()
        if not fails:
            del table[key]
            return deque()
        return fails

    def _wait(self, table: OrderedDict, key: str, maximum: int) -> int:
        fails = self._recent(table, key)
        if len(fails) < maximum:
            return 0
        # Bloqueado hasta que el fallo que completa el máximo salga de la ventana.
        return max(1, math.ceil(fails[-maximum] + self._window() - self._clock()))

    def check(self, username: str, origin: str) -> int:
        """Segundos que hay que esperar (0: se puede intentar). Se consulta antes de verificar la contraseña."""
        return max(
            self._wait(self._users, username, settings.login_max_attempts),
            self._wait(self._origins, origin, settings.login_max_attempts_per_origin),
        )

    def _add(self, table: OrderedDict, key: str) -> None:
        fails = table.pop(key, None) or deque()
        fails.append(self._clock())
        table[key] = fails
        while len(table) > self._max:
            table.popitem(last=False)

    def fail(self, username: str, origin: str) -> None:
        self._add(self._users, username)
        self._add(self._origins, origin)

    def clear_user(self, username: str) -> None:
        self._users.pop(username, None)

    def reset(self) -> None:
        self._users.clear()
        self._origins.clear()


# Instancia que comparten las rutas.
login_throttle = LoginThrottle()


def client_origin(request) -> str:
    """Desde dónde llega la petición: la dirección directa, o con `TRUST_FORWARDED_FOR=on` el **último** valor de
    X-Forwarded-For (el que agrega el proxy de confianza; el primero lo puede escribir cualquiera)."""
    if (settings.trust_forwarded_for or "").strip().lower() == "on":
        forwarded = request.headers.get("x-forwarded-for", "")
        values = [v.strip() for v in forwarded.split(",") if v.strip()]
        if values:
            return values[-1]
    client = getattr(request, "client", None)
    return client.host if client and client.host else "desconocido"
