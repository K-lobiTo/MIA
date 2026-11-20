"""Lector de páginas web (feature 022).

`PageFetcher` es la interfaz (el punto de extensión por si algún día se lee con un navegador) y `HttpPageFetcher` la
implementación con `httpx`. Lee **una** dirección y sus redirecciones: nunca sigue los enlaces de la página. Cada salto se
valida contra la red interna y la conexión va a la IP ya validada, con el nombre del sitio en `Host` y en el SNI de TLS
(research R2 y R3). Devuelve la última respuesta sea cual sea su estado: decidir si sirve es de `detect.py`.

Solo se piden `robots.txt`, la dirección y sus redirecciones: la página se lee como texto y `extract.py` no devuelve
direcciones para visitar."""

import re
import socket
import ssl
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from urllib import robotparser
from urllib.parse import urljoin, urlsplit

import httpx

from mia.config import settings
from mia.ingestion.web.errors import WebRejection, rechazo
from mia.ingestion.web.urls import (
    PUERTOS_POR_DEFECTO,
    clave_de_comparacion,
    normalizar_entrada,
    resolver_publica,
)

REDIRECCIONES = {301, 302, 303, 307, 308}
ROBOTS_MAX_BYTES = 256 * 1024
ROBOTS_MAX_REDIRECCIONES = 3
TOKEN_ROBOTS = "MIA-Lector"


@dataclass
class FetchedPage:
    """La última respuesta de una lectura: dirección final, estado, cabeceras (en minúscula), cuerpo ya descomprimido,
    el `Content-Type` completo y la codificación declarada en él."""

    url_final: str
    estado: int
    cabeceras: dict[str, str] = field(default_factory=dict)
    cuerpo: bytes = b""
    tipo_contenido: str = ""
    codificacion: str | None = None


class PageFetcher(ABC):
    @abstractmethod
    def fetch(self, url: str) -> FetchedPage:
        """Lee la dirección. Lanza `WebRejection` si no se puede leer."""
        ...


def _es_tls(error: BaseException | None) -> bool:
    visto = set()
    while error is not None and id(error) not in visto:
        if isinstance(error, ssl.SSLError):
            return True
        visto.add(id(error))
        error = error.__cause__ or error.__context__
    return False


def _codificacion(tipo: str) -> str | None:
    coincide = re.search(r"charset\s*=\s*[\"']?([\w.\-:]+)", tipo, re.IGNORECASE)
    return coincide.group(1).lower() if coincide else None


class HttpPageFetcher(PageFetcher):
    def __init__(
        self,
        resolver: Callable = socket.getaddrinfo,
        transporte: httpx.BaseTransport | None = None,
        reloj: Callable[[], float] = time.monotonic,
    ):
        self.resolver = resolver
        self.transporte = transporte
        self.reloj = reloj

    def fetch(self, url: str) -> FetchedPage:
        # Solo se piden la dirección y sus redirecciones: nunca los enlaces, las imágenes ni los archivos de la página.
        url = normalizar_entrada(url)
        inicio = self.reloj()
        vistas = {clave_de_comparacion(url)}
        robots: dict[str, robotparser.RobotFileParser | None] = {}  # una consulta por origen en cada intento
        saltos = 0
        while True:
            self._exigir_robots(url, inicio, robots)
            estado, cabeceras, cuerpo = self._pedir(url, inicio, settings.web_max_page_kb * 1024)
            destino = cabeceras.get("location")
            if estado in REDIRECCIONES and destino:
                saltos += 1
                if saltos > settings.web_max_redirects:
                    raise rechazo("too_many_redirects")
                url = normalizar_entrada(urljoin(url, destino))
                clave = clave_de_comparacion(url)
                if clave in vistas:
                    raise rechazo("too_many_redirects")
                vistas.add(clave)
                continue
            tipo = cabeceras.get("content-type", "")
            return FetchedPage(url, estado, cabeceras, cuerpo, tipo, _codificacion(tipo))

    def _pedir(
        self, url: str, inicio: float, tope: int, truncar: bool = False
    ) -> tuple[int, dict[str, str], bytes]:
        """Una petición GET a la IP ya validada de `url`. Respeta el plazo total y el tope de bytes ya descomprimidos."""
        partes = urlsplit(url)
        anfitrion = partes.hostname or ""
        puerto = partes.port or PUERTOS_POR_DEFECTO[partes.scheme]
        ip = resolver_publica(anfitrion, puerto, self.resolver)

        restante = settings.web_fetch_timeout_seconds - (self.reloj() - inicio)
        if restante <= 0:
            raise rechazo("unreachable")
        sitio = f"[{ip}]" if ":" in ip else ip
        ruta = (partes.path or "/") + (f"?{partes.query}" if partes.query else "")
        destino = f"{partes.scheme}://{sitio}:{puerto}{ruta}"
        nombre = f"[{anfitrion}]" if ":" in anfitrion else anfitrion
        cabecera_host = nombre if puerto == PUERTOS_POR_DEFECTO[partes.scheme] else f"{nombre}:{puerto}"
        cabeceras = {
            "Host": cabecera_host,
            "User-Agent": settings.web_user_agent,
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.1",
            "Accept-Language": "es",
            # Sin compresión: una respuesta que se expande mucho no puede agotar la memoria (y si el sitio comprime de todos
            # modos, los bytes se cuentan ya descomprimidos).
            "Accept-Encoding": "identity",
        }
        plazos = httpx.Timeout(connect=min(5.0, restante), read=min(10.0, restante), write=min(10.0, restante), pool=restante)
        try:
            # Un cliente nuevo por salto: sin cookies compartidas y, con `trust_env=False`, sin proxies del entorno que
            # esquivarían la conexión a la IP validada.
            with httpx.Client(
                transport=self.transporte, follow_redirects=False, timeout=plazos, trust_env=False
            ) as cliente, cliente.stream(
                "GET", destino, headers=cabeceras, extensions={"sni_hostname": anfitrion}
            ) as respuesta:
                return self._leer(respuesta, inicio, tope, truncar)
        except httpx.HTTPError as error:
            if _es_tls(error):
                raise rechazo("tls_error") from error
            raise rechazo("unreachable") from error
        except ssl.SSLError as error:
            raise rechazo("tls_error") from error

    def _leer(
        self, respuesta: httpx.Response, inicio: float, tope: int, truncar: bool
    ) -> tuple[int, dict[str, str], bytes]:
        cabeceras = {clave.lower(): valor for clave, valor in respuesta.headers.items()}
        if respuesta.status_code in REDIRECCIONES and cabeceras.get("location"):
            self._revisar_plazo(inicio)
            return respuesta.status_code, cabeceras, b""
        largo = cabeceras.get("content-length", "")
        if not truncar and largo.isdigit() and int(largo) > tope and "content-encoding" not in cabeceras:
            raise rechazo("too_large")
        cuerpo = bytearray()
        for bloque in respuesta.iter_bytes():
            cuerpo += bloque
            if len(cuerpo) > tope:
                if truncar:  # robots.txt: se usa lo que cabe, no se rechaza
                    cuerpo = cuerpo[:tope]
                    break
                raise rechazo("too_large")
            self._revisar_plazo(inicio)
        self._revisar_plazo(inicio)
        return respuesta.status_code, cabeceras, bytes(cuerpo)

    def _exigir_robots(self, url: str, inicio: float, cache: dict) -> None:
        """`robots_disallowed` si el sitio no permite leer esa ruta (research R4, RFC 9309). La consulta es una por origen y por
        intento; si cambia el origen por una redirección, se consulta el del nuevo origen antes de pedir ese salto."""
        partes = urlsplit(url)
        origen = f"{partes.scheme}://{partes.netloc}"
        if origen not in cache:
            # Un nombre que no resuelve (o que apunta a la red interna) se informa como tal, no como un robots.txt prohibido.
            resolver_publica(partes.hostname or "", partes.port or PUERTOS_POR_DEFECTO[partes.scheme], self.resolver)
            cache[origen] = self._leer_robots(origen, inicio)
        reglas = cache[origen]
        if reglas is not None and not reglas.can_fetch(TOKEN_ROBOTS, url):
            raise rechazo("robots_disallowed")

    def _leer_robots(self, origen: str, inicio: float) -> robotparser.RobotFileParser | None:
        """Las reglas del sitio, o None si no tiene (cualquier 4xx: sin restricciones). 5xx, tiempo agotado o error de red se
        tratan como prohibido, como pide el RFC 9309."""
        direccion = f"{origen}/robots.txt"
        try:
            for _ in range(ROBOTS_MAX_REDIRECCIONES + 1):
                estado, cabeceras, cuerpo = self._pedir(direccion, inicio, ROBOTS_MAX_BYTES, truncar=True)
                if estado in REDIRECCIONES and cabeceras.get("location"):
                    direccion = normalizar_entrada(urljoin(direccion, cabeceras["location"]))
                    continue
                break
            else:
                raise rechazo("robots_disallowed")
        except WebRejection as error:
            if error.code in ("unreachable", "tls_error"):
                raise rechazo("robots_disallowed") from error
            raise
        if 400 <= estado < 500:
            return None
        if estado >= 300:
            raise rechazo("robots_disallowed")
        reglas = robotparser.RobotFileParser()
        reglas.parse(cuerpo.decode("utf-8", errors="ignore").splitlines())
        return reglas

    def _revisar_plazo(self, inicio: float) -> None:
        if self.reloj() - inicio > settings.web_fetch_timeout_seconds:
            raise rechazo("unreachable")


def get_page_fetcher(nombre: str = "http") -> PageFetcher:
    if nombre == "http":
        return HttpPageFetcher()
    raise ValueError(f"Lector de páginas no soportado: {nombre}")
