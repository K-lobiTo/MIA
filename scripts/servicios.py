#!/usr/bin/env python3
"""Enciende, apaga y consulta el estado de los servicios de MIA en Railway.

Los cuatro servicios no se redespliegan solos (Railway no tiene instalada su aplicación de GitHub):
encender es `railway up` desde esta carpeta y apagar es `railway down` (equivale a "Remove" en el
panel de Railway). Apagar no borra nada: se conservan variables, dominios y datos (Neon y Qdrant
viven fuera de Railway). Ver "Desplegar cambios" en docs/OPERACION.md.

Uso (desde la raíz del repositorio, con la CLI de Railway iniciada y vinculada: `railway login`
y `railway link`):
    python scripts/servicios.py estado
    python scripts/servicios.py encender                    # los cuatro, la API primero
    python scripts/servicios.py encender mia-computacion    # solo uno (o varios)
    python scripts/servicios.py apagar                      # los cuatro, la API al final
    python scripts/servicios.py apagar mia-panel

Los nombres válidos: MIA (la API), mia-computacion, mia-administracion y mia-panel. Los sitios
necesitan la API encendida para funcionar.

`encender` sube los archivos de la carpeta local (respeta .gitignore, así que .env* y tmp/ no se
suben): avisa si hay cambios sin commitear y pide confirmación (--forzar la omite). Espera a que
cada servicio termine de desplegar y comprueba que responda.

Solo usa la biblioteca estándar.
"""

import argparse
import json
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

RAIZ_REPO = Path(__file__).resolve().parents[1]
ESPERA_MAXIMA_S = 600
TERMINADOS = {"SUCCESS", "FAILED", "CRASHED", "REMOVED"}


@dataclass(frozen=True)
class Servicio:
    nombre: str  # el de Railway
    url: str
    ruta_salud: str
    descripcion: str


# La API va primero: los sitios llaman a la API, y al apagar se deja para el final.
SERVICIOS = [
    Servicio("MIA", "https://mia-main.up.railway.app", "/health", "API"),
    Servicio("mia-computacion", "https://mia-computacion.up.railway.app", "/", "Consulta de Computación"),
    Servicio(
        "mia-administracion",
        "https://mia-administracion.up.railway.app",
        "/",
        "Consulta de Administración de Empresas",
    ),
    Servicio("mia-panel", "https://mia-panel.up.railway.app", "/", "Panel de administración"),
]
POR_NOMBRE = {s.nombre.lower(): s for s in SERVICIOS}


def seleccionar(nombres: list[str], invertir: bool = False) -> list[Servicio]:
    """Los servicios pedidos (todos si no se pide ninguno), en el orden de SERVICIOS o al revés."""
    if not nombres:
        elegidos = list(SERVICIOS)
    else:
        desconocidos = [n for n in nombres if n.lower() not in POR_NOMBRE]
        if desconocidos:
            validos = ", ".join(s.nombre for s in SERVICIOS)
            raise ValueError(f"Servicio desconocido: {', '.join(desconocidos)}. Los válidos: {validos}.")
        pedidos = {POR_NOMBRE[n.lower()].nombre for n in nombres}
        elegidos = [s for s in SERVICIOS if s.nombre in pedidos]
    return list(reversed(elegidos)) if invertir else elegidos


def railway(*args: str, revisar: bool = True) -> subprocess.CompletedProcess:
    resultado = subprocess.run(["railway", *args], capture_output=True, text=True, cwd=RAIZ_REPO, check=False)
    if revisar and resultado.returncode != 0:
        detalle = (resultado.stderr or resultado.stdout).strip().splitlines()
        raise RuntimeError(f"railway {' '.join(args)} falló: {detalle[-1] if detalle else 'sin detalle'}")
    return resultado


def ultimo_despliegue(servicio: Servicio) -> dict | None:
    salida = railway("deployment", "list", "-s", servicio.nombre, "--json", revisar=False)
    try:
        lista = json.loads(salida.stdout)
    except json.JSONDecodeError:
        return None
    return lista[0] if lista else None


def codigo_http(servicio: Servicio) -> int:
    """Código HTTP de la dirección pública (200: encendido; 404: apagado); 0 si no hay conexión."""
    try:
        with urllib.request.urlopen(servicio.url + servicio.ruta_salud, timeout=15) as respuesta:
            return respuesta.status
    except urllib.error.HTTPError as error:
        return error.code
    except (urllib.error.URLError, TimeoutError, OSError):
        return 0


def hay_cambios_sin_commitear() -> bool:
    salida = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, cwd=RAIZ_REPO, check=False)
    return bool(salida.stdout.strip())


def rama_actual() -> str:
    salida = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True, cwd=RAIZ_REPO, check=False)
    return salida.stdout.strip() or "(sin rama)"


def confirmar(pregunta: str) -> bool:
    return input(f"{pregunta} [s/N] ").strip().lower() in {"s", "si", "sí", "y", "yes"}


def esperar_despliegue(servicio: Servicio, id_anterior: str | None) -> str:
    """Espera a que aparezca y termine el despliegue nuevo; devuelve su estado final."""
    limite = time.monotonic() + ESPERA_MAXIMA_S
    while time.monotonic() < limite:
        actual = ultimo_despliegue(servicio)
        if actual and actual["id"] != id_anterior and actual["status"] in TERMINADOS:
            return actual["status"]
        time.sleep(10)
    return "TIEMPO_AGOTADO"


def encender(servicios: list[Servicio], forzar: bool, esperar: bool) -> int:
    print(f"Se subirá lo que hay en esta carpeta (rama {rama_actual()}).")
    if hay_cambios_sin_commitear():
        print("AVISO: hay cambios sin commitear; también se publicarán.")
        if not forzar and not confirmar("¿Continuar?"):
            print("Cancelado.")
            return 1
    elif not forzar and not confirmar("¿Encender " + ", ".join(s.nombre for s in servicios) + "?"):
        print("Cancelado.")
        return 1

    fallos = 0
    for servicio in servicios:
        anterior = ultimo_despliegue(servicio)
        print(f"\n{servicio.nombre} ({servicio.descripcion}): subiendo...")
        railway("up", "-s", servicio.nombre, "--detach")
        if not esperar:
            print("  lanzado (sin esperar).")
            continue
        estado = esperar_despliegue(servicio, anterior["id"] if anterior else None)
        codigo = codigo_http(servicio) if estado == "SUCCESS" else 0
        if estado == "SUCCESS" and codigo == 200:
            print(f"  encendido: {estado}, {servicio.url}{servicio.ruta_salud} responde {codigo}.")
        else:
            fallos += 1
            print(f"  PROBLEMA: despliegue {estado}, la dirección responde {codigo}. Ver los logs: railway logs -s {servicio.nombre}")
    print("\nTodo encendido." if not fallos else f"\n{fallos} servicio(s) con problemas.")
    return 1 if fallos else 0


def apagar(servicios: list[Servicio], forzar: bool) -> int:
    nombres = ", ".join(s.nombre for s in servicios)
    api_incluida = any(s.nombre == "MIA" for s in servicios)
    aviso = " (incluye la API: sin ella los sitios no funcionan)" if api_incluida else ""
    if not forzar and not confirmar(f"¿Apagar {nombres}{aviso}?"):
        print("Cancelado.")
        return 1
    for servicio in servicios:
        railway("down", "-s", servicio.nombre, "-y")
        print(f"{servicio.nombre}: apagado (se conserva su configuración).")
    return 0


def estado(servicios: list[Servicio]) -> int:
    print(f"{'Servicio':<20} {'Último despliegue':<18} {'HTTP':<5} Dirección")
    for servicio in servicios:
        despliegue = ultimo_despliegue(servicio)
        etiqueta = despliegue["status"] if despliegue else "sin despliegues"
        print(f"{servicio.nombre:<20} {etiqueta:<18} {codigo_http(servicio):<5} {servicio.url}")
    print("\nHTTP 200: encendido. 404: apagado. 502: encendido pero mal configurado (puerto).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Enciende, apaga y consulta los servicios de MIA en Railway.")
    parser.add_argument("accion", choices=["estado", "encender", "apagar"])
    parser.add_argument("servicios", nargs="*", help="MIA, mia-computacion, mia-administracion, mia-panel (por defecto, todos)")
    parser.add_argument("--forzar", action="store_true", help="no pedir confirmación")
    parser.add_argument("--sin-esperar", action="store_true", help="con encender: lanzar los despliegues sin esperar su resultado")
    args = parser.parse_args()

    if shutil.which("railway") is None:
        print("No se encontró la CLI de Railway. Instalarla con: npm install -g @railway/cli", file=sys.stderr)
        return 2
    try:
        elegidos = seleccionar(args.servicios, invertir=args.accion == "apagar")
        if args.accion == "estado":
            return estado(elegidos)
        if args.accion == "encender":
            return encender(elegidos, args.forzar, esperar=not args.sin_esperar)
        return apagar(elegidos, args.forzar)
    except (ValueError, RuntimeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
