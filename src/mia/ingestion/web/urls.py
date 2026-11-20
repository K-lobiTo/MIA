"""Direcciones de la lectura de una página web (feature 022).

Validación de lo que escribe la persona, clave para comparar direcciones y comprobación de que un nombre no apunta a la red
interna del servidor (SSRF). Nada de aquí hace peticiones: la resolución de nombres se inyecta para poder probarla sin red.
Ver specs/022-ingesta-web-basica/research.md (R3 y R8)."""

import ipaddress
import re
import socket
from collections.abc import Callable, Iterable
from urllib.parse import urlsplit, urlunsplit

from mia.ingestion.web.errors import rechazo

MAX_LARGO = 2048
ESQUEMAS = {"http", "https"}
PUERTOS_POR_DEFECTO = {"http": 80, "https": 443}
NO_INTERPRETABLE = "(dirección no interpretable)"

_ESQUEMA = re.compile(r"^([A-Za-z][A-Za-z0-9+.\-]*):(.*)$", re.DOTALL)
_PUERTO_SOLO = re.compile(r"^\d+(?:[/?#]|$)")
# NAT64 (64:ff9b::/96) lleva una IPv4 en sus últimos 32 bits.
_NAT64 = ipaddress.ip_network("64:ff9b::/96")


def normalizar_entrada(texto: str | None) -> str:
    """La dirección absoluta (`http` o `https`) a partir de lo que escribió la persona, o `invalid_url`."""
    texto = (texto or "").strip()
    if not texto or len(texto) > MAX_LARGO or any(c.isspace() for c in texto):
        raise rechazo("invalid_url")

    if "://" not in texto:
        coincide = _ESQUEMA.match(texto)
        if coincide and not _PUERTO_SOLO.match(coincide.group(2)):
            # `javascript:`, `mailto:`, `data:` y similares no son direcciones web.
            raise rechazo("invalid_url")
        sitio = re.split(r"[/?#]", texto, maxsplit=1)[0]
        if "." not in sitio:
            raise rechazo("invalid_url")
        texto = "https://" + texto

    try:
        partes = urlsplit(texto)
        puerto = partes.port
        anfitrion = partes.hostname
    except ValueError:
        raise rechazo("invalid_url") from None
    if partes.scheme.lower() not in ESQUEMAS or not anfitrion:
        raise rechazo("invalid_url")
    if partes.username is not None or partes.password is not None or "@" in partes.netloc:
        raise rechazo("invalid_url")  # no se aceptan credenciales en la dirección
    if puerto is not None and puerto == 0:
        raise rechazo("invalid_url")
    try:
        anfitrion = anfitrion.encode("idna").decode("ascii")
    except UnicodeError:
        raise rechazo("invalid_url") from None

    sitio = f"[{anfitrion}]" if ":" in anfitrion else anfitrion
    if puerto is not None:
        sitio += f":{puerto}"
    return urlunsplit((partes.scheme.lower(), sitio.lower(), partes.path, partes.query, ""))


def clave_de_comparacion(url: str) -> str:
    """Clave con la que se decide si dos direcciones son la misma página: el esquema no cuenta (`http` y `https`
    equivalen), el servidor va en minúscula y sin el puerto por defecto, sin fragmento, la ruta sin la barra final y la
    consulta tal cual. `www.` sí cuenta: un sitio puede servir contenido distinto (research R8)."""
    partes = urlsplit(url.strip())
    anfitrion = (partes.hostname or "").lower()
    try:
        puerto = partes.port
    except ValueError:
        puerto = None
    if puerto is not None and puerto != PUERTOS_POR_DEFECTO.get(partes.scheme.lower()):
        anfitrion += f":{puerto}"
    ruta = partes.path.rstrip("/")
    return anfitrion + ruta + (f"?{partes.query}" if partes.query else "")


def _es_publica(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:
            return _es_publica(ip.ipv4_mapped)
        if ip in _NAT64:
            return _es_publica(ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF))
    if ip.is_multicast or ip.is_unspecified or ip.is_loopback or ip.is_link_local or ip.is_reserved:
        return False
    return ip.is_global


def exigir_ip_publica(ips: Iterable[str]) -> None:
    """`private_address` si alguna IP es privada, de bucle local, de enlace local, reservada, compartida, de multidifusión o
    no especificada (incluidas IPv6 y las IPv4 mapeadas a IPv6)."""
    for texto in ips:
        try:
            ip = ipaddress.ip_address(texto.split("%", 1)[0])
        except ValueError:
            raise rechazo("private_address") from None
        if not _es_publica(ip):
            raise rechazo("private_address")


def resolver_publica(nombre: str, puerto: int, resolver: Callable = socket.getaddrinfo) -> str:
    """Resuelve el nombre, exige que **todas** sus IP sean públicas y devuelve la primera. Esa es la IP a la que se conecta
    el lector, para que una segunda resolución (rebinding de DNS) no pueda llevarlo a otra (research R2)."""
    try:
        informacion = resolver(nombre, puerto, type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError, OSError):
        raise rechazo("unreachable") from None
    ips = [dato[4][0] for dato in informacion]
    if not ips:
        raise rechazo("unreachable")
    exigir_ip_publica(ips)
    return ips[0]


def direccion_para_auditoria(url: str) -> str:
    """La dirección tal como se registra: sin consulta, fragmento ni credenciales (pueden llevar tokens o datos personales).
    Una que no se puede interpretar devuelve un texto fijo, nunca lo escrito. No lanza."""
    try:
        partes = urlsplit((url or "").strip())
        anfitrion = partes.hostname
        puerto = partes.port
    except ValueError:
        return NO_INTERPRETABLE
    if partes.scheme.lower() not in ESQUEMAS or not anfitrion:
        return NO_INTERPRETABLE
    sitio = f"[{anfitrion}]" if ":" in anfitrion else anfitrion
    if puerto is not None:
        sitio += f":{puerto}"
    return urlunsplit((partes.scheme.lower(), sitio, partes.path, "", ""))
