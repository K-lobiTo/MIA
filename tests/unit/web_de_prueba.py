"""Ayudas de prueba de la feature 022 (ingesta de una página web). Ninguna abre un socket: la resolución de nombres y el
transporte de `httpx` se sustituyen por versiones simuladas, y las páginas son HTML inventado de `tests/fixtures/web/`."""

import ipaddress
import socket
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

import httpx

CARPETA = Path(__file__).resolve().parent.parent / "fixtures" / "web"

IP_PUBLICA = "93.184.216.34"


def pagina(nombre: str) -> str:
    """Texto (UTF-8) de una página de prueba."""
    return (CARPETA / nombre).read_text(encoding="utf-8")


def pagina_cp1252(nombre: str) -> bytes:
    """La misma página recodificada a Windows-1252 (no se guarda como binario en el repositorio)."""
    return pagina(nombre).encode("cp1252")


def resolver_de(tabla: dict[str, list[str]] | None = None):
    """Función con la firma de `socket.getaddrinfo` que resuelve solo lo que dice `tabla` (nombre a lista de IP). Una IP
    escrita como dirección se devuelve tal cual, como hace `getaddrinfo`; cualquier otro nombre lanza `gaierror`."""
    tabla = tabla or {}

    def resolver(host, puerto, family=0, type=0, proto=0, flags=0):
        if host in tabla:
            ips = tabla[host]
        else:
            try:
                ips = [str(ipaddress.ip_address(host))]
            except ValueError:
                raise socket.gaierror(socket.EAI_NONAME, f"no se resuelve {host}") from None
        salida = []
        for ip in ips:
            if ":" in ip:
                salida.append((socket.AF_INET6, socket.SOCK_STREAM, 6, "", (ip, puerto or 0, 0, 0)))
            else:
                salida.append((socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, puerto or 0)))
        return salida

    return resolver


def resolver_publico(*nombres: str):
    """Resuelve cada nombre dado a una IP pública."""
    return resolver_de({nombre: [IP_PUBLICA] for nombre in nombres})


@dataclass
class Respuesta:
    estado: int = 200
    cabeceras: dict[str, str] | None = None
    cuerpo: str | bytes | Iterable[bytes] = ""


@dataclass
class Peticion:
    metodo: str
    url: str  # la que realmente se pide (con la IP validada)
    host: str  # cabecera Host
    sni: str | None  # extensión sni_hostname
    url_logica: str  # esquema, nombre del sitio y ruta, sin la IP
    cabeceras: dict[str, str] = field(default_factory=dict)


class TransporteRegistrado(httpx.MockTransport):
    """`httpx.MockTransport` que registra cada petición en `.peticiones`."""

    def __init__(self, rutas: dict, por_defecto: Respuesta | None = None):
        self.peticiones: list[Peticion] = []
        self._rutas = rutas
        self._por_defecto = por_defecto or Respuesta(404, None, "CONTENIDO-AJENO")
        super().__init__(self._atender)

    def _atender(self, request: httpx.Request) -> httpx.Response:
        host = request.headers.get("host", request.url.host)
        esquema = request.url.scheme
        ruta = request.url.raw_path.decode()
        logica = f"{esquema}://{host}{ruta}"
        self.peticiones.append(
            Peticion(
                request.method,
                str(request.url),
                host,
                request.extensions.get("sni_hostname"),
                logica,
                dict(request.headers),
            )
        )
        destino = self._rutas.get(logica)
        if destino is None and logica.endswith("/robots.txt"):
            destino = Respuesta(404, None, "")
        if destino is None:
            destino = self._por_defecto
        if callable(destino):
            destino = destino(request)
        if isinstance(destino, Exception):
            raise destino
        cuerpo = destino.cuerpo
        if isinstance(cuerpo, str):
            cuerpo = cuerpo.encode("utf-8")
        return httpx.Response(destino.estado, headers=destino.cabeceras or {}, content=cuerpo, request=request)

    def logicas(self) -> list[str]:
        """Direcciones pedidas, en orden, sin la IP."""
        return [p.url_logica for p in self.peticiones]


def transporte(rutas: dict, por_defecto: Respuesta | None = None) -> TransporteRegistrado:
    """Transporte simulado: `rutas` mapea la dirección completa (`https://ejemplo.test/programa`) a una `Respuesta`, a una
    función `(request) -> Respuesta` o a una excepción que se lanza. `robots.txt` sin ruta responde 404 (sin
    restricciones) y cualquier otra dirección desconocida responde 404 con `CONTENIDO-AJENO`."""
    return TransporteRegistrado(rutas, por_defecto)


def html(cuerpo: str, estado: int = 200, tipo: str = "text/html; charset=utf-8", **cabeceras) -> Respuesta:
    return Respuesta(estado, {"content-type": tipo, **cabeceras}, cuerpo)


def pagina_leida(
    cuerpo: str | bytes,
    url: str = "https://ejemplo.test/programa",
    estado: int = 200,
    tipo: str = "text/html; charset=utf-8",
    cabeceras: dict | None = None,
    codificacion: str | None = "utf-8",
):
    """`FetchedPage` armada a mano, para las pruebas de la detección y de la ruta."""
    from mia.ingestion.web.fetcher import FetchedPage

    datos = cuerpo.encode("utf-8") if isinstance(cuerpo, str) else cuerpo
    todas = {"content-type": tipo, **(cabeceras or {})}
    return FetchedPage(
        url_final=url, estado=estado, cabeceras=todas, cuerpo=datos, tipo_contenido=tipo, codificacion=codificacion
    )


class FetcherFalso:
    """Sustituye al lector de páginas en las pruebas de la ruta: devuelve (o lanza) lo que dice `paginas` y registra las
    direcciones que se le pidieron en `.pedidas`."""

    def __init__(self, paginas: dict | Callable | None = None):
        self.paginas = paginas or {}
        self.pedidas: list[str] = []

    def fetch(self, url: str):
        from mia.ingestion.web.errors import rechazo

        self.pedidas.append(url)
        if callable(self.paginas):
            resultado = self.paginas(url)
        else:
            resultado = self.paginas.get(url)
            if resultado is None and urlsplit(url).scheme == "":
                resultado = self.paginas.get("https://" + url)
        if resultado is None:
            raise rechazo("unreachable")
        if isinstance(resultado, Exception):
            raise resultado
        return resultado
