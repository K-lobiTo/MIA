#!/usr/bin/env python3
"""Enciende, apaga y consulta el estado de los servicios de MIA en Railway.

Los cinco servicios no se redespliegan solos (Railway no tiene instalada su aplicación de GitHub):
encender es `railway up` desde esta carpeta y apagar es `railway down` (equivale a "Remove" en el
panel de Railway). Apagar no borra nada: se conservan variables, dominios y datos (Neon y Qdrant
viven fuera de Railway). Ver "Desplegar cambios" en docs/OPERACION.md.

Uso (desde la raíz del repositorio, con la CLI de Railway iniciada y vinculada: `railway login`
y `railway link`):
    python scripts/servicios.py estado
    python scripts/servicios.py encender                    # los cinco, la API primero
    python scripts/servicios.py encender mia-computacion    # solo uno (o varios)
    python scripts/servicios.py apagar                      # los cinco, la API al final
    python scripts/servicios.py apagar mia-panel

Los nombres válidos: MIA (la API), mia-whatsapp (el bot de WhatsApp), mia-computacion,
mia-analitica-negocios y mia-panel. Los sitios y el bot necesitan la API encendida para funcionar.

`encender` despliega por defecto lo que hay en `main` de GitHub (`origin/main`, tras un `git fetch`),
no lo que haya en la carpeta local: exporta esa versión del repositorio a una carpeta temporal y la
sube de ahí, así el trabajo de `dev` sin fusionar no llega a producción por accidente. Con `--ref`
se elige otra rama o commit publicado (p. ej. `--ref origin/dev`), y con `--local` se sube la carpeta
actual tal cual (respeta .gitignore, así que .env* y tmp/ no se suben; avisa si hay cambios sin
commitear). Pide confirmación (--forzar la omite), espera a que cada servicio termine de desplegar y
comprueba que responda.

Otra cuenta de Railway: `scripts/crear_servicios.py` crea los cinco servicios y escribe `servicios.local.json`
(ignorado por git) con las direcciones de esa cuenta y `"subir_carpeta": true`. Con ese archivo, este script usa
esas direcciones y sube cada servicio desde su propia carpeta (`whatsapp/`, `web/consulta/`, `web/admin/`), así que
no hace falta configurar *Root Directory* en Railway. Sin el archivo todo funciona como antes (cuenta original).

Ojo con la base de datos: la API migra la base al arrancar. Desplegar una versión con menos
migraciones que las que ya tiene la base (p. ej. `main` sobre una base ya migrada por `dev`) hace que
la API no arranque; hay que devolver antes la base con `alembic downgrade`. Ver "Desplegar cambios" en
docs/OPERACION.md.

Solo usa la biblioteca estándar.
"""

import argparse
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, replace
from pathlib import Path

RAIZ_REPO = Path(__file__).resolve().parents[1]
ESPERA_MAXIMA_S = 600
REF_POR_DEFECTO = "origin/main"
TERMINADOS = {"SUCCESS", "FAILED", "CRASHED", "REMOVED"}
ARCHIVO_CONFIG = RAIZ_REPO / "servicios.local.json"


@dataclass(frozen=True)
class Servicio:
    nombre: str  # el de Railway
    url: str
    ruta_salud: str
    descripcion: str
    carpeta: str = ""  # carpeta del repositorio que se sube cuando "subir_carpeta" está activo ("" es la raíz)


# La API va primero: los sitios y el bot llaman a la API, y al apagar se deja para el final.
SERVICIOS = [
    Servicio("MIA", "https://mia-main.up.railway.app", "/health", "API"),
    Servicio("mia-whatsapp", "https://mia-whatsapp.up.railway.app", "/health", "Bot de WhatsApp (Kapso)", "whatsapp"),
    Servicio(
        "mia-computacion",
        "https://mia-computacion.up.railway.app",
        "/",
        "Consulta de la Unidad de Postgrados de Computación",
        "web/consulta",
    ),
    Servicio(
        "mia-analitica-negocios",
        "https://mia-analitica-negocio.up.railway.app",
        "/",
        "Consulta del Área académica de Analítica de Negocios",
        "web/consulta",
    ),
    Servicio("mia-panel", "https://mia-panel.up.railway.app", "/", "Panel de administración", "web/admin"),
]
POR_NOMBRE = {s.nombre.lower(): s for s in SERVICIOS}


def cargar_configuracion(ruta: Path = ARCHIVO_CONFIG) -> dict:
    """Lee `servicios.local.json` (vacío si no existe): {"urls": {"MIA": "https://..."}, "subir_carpeta": true}."""
    if not ruta.exists():
        return {}
    try:
        config = json.loads(ruta.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"{ruta.name} no es un JSON válido: {error}") from error
    if not isinstance(config, dict):
        raise ValueError(f"{ruta.name} debe ser un objeto JSON.")  # noqa: TRY004 (main atrapa ValueError)
    desconocidos = [n for n in config.get("urls", {}) if n.lower() not in POR_NOMBRE]
    if desconocidos:
        raise ValueError(f"{ruta.name}: servicios desconocidos en \"urls\": {', '.join(desconocidos)}.")
    return config


def aplicar_configuracion(config: dict) -> list[Servicio]:
    """El catálogo de servicios con las direcciones de la configuración (las que no aparecen quedan como están)."""
    urls = {nombre.lower(): url.rstrip("/") for nombre, url in config.get("urls", {}).items()}
    return [replace(s, url=urls.get(s.nombre.lower(), s.url)) for s in SERVICIOS]


def seleccionar(nombres: list[str], invertir: bool = False, catalogo: list[Servicio] | None = None) -> list[Servicio]:
    """Los servicios pedidos (todos si no se pide ninguno), en el orden del catálogo o al revés."""
    catalogo = catalogo if catalogo is not None else SERVICIOS
    por_nombre = {s.nombre.lower(): s for s in catalogo}
    if not nombres:
        elegidos = list(catalogo)
    else:
        desconocidos = [n for n in nombres if n.lower() not in por_nombre]
        if desconocidos:
            validos = ", ".join(s.nombre for s in catalogo)
            raise ValueError(f"Servicio desconocido: {', '.join(desconocidos)}. Los válidos: {validos}.")
        pedidos = {por_nombre[n.lower()].nombre for n in nombres}
        elegidos = [s for s in catalogo if s.nombre in pedidos]
    return list(reversed(elegidos)) if invertir else elegidos


def carpeta_de_subida(servicio: Servicio, base: Path, subir_carpeta: bool) -> Path:
    """Desde dónde se sube un servicio: la base (raíz del repositorio o su exportación), o con `subir_carpeta`
    la carpeta propia del servicio, que tiene su `Dockerfile` y funciona sin *Root Directory* en Railway."""
    return base / servicio.carpeta if subir_carpeta and servicio.carpeta else base


def railway(*args: str, revisar: bool = True, cwd: Path | None = None) -> subprocess.CompletedProcess:
    resultado = subprocess.run(["railway", *args], capture_output=True, text=True, cwd=cwd or RAIZ_REPO, check=False)
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


def git(*args: str, repo: Path = RAIZ_REPO) -> str:
    resultado = subprocess.run(["git", *args], capture_output=True, text=True, cwd=repo, check=False)
    if resultado.returncode != 0:
        detalle = (resultado.stderr or resultado.stdout).strip().splitlines()
        raise RuntimeError(f"git {' '.join(args)} falló: {detalle[-1] if detalle else 'sin detalle'}")
    return resultado.stdout.strip()


def resolver_ref(ref: str, repo: Path = RAIZ_REPO) -> tuple[str, str]:
    """Commit (abreviado) y asunto de una referencia del repositorio; falla si no existe."""
    commit = git("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}", repo=repo)
    return commit[:9], git("log", "-1", "--format=%s", commit, repo=repo)


def exportar_ref(ref: str, destino: Path, repo: Path = RAIZ_REPO) -> None:
    """Deja en `destino` los archivos versionados de `ref` (sin .git ni nada ignorado o sin commitear)."""
    archivo = destino.parent / (destino.name + ".tar")
    git("archive", "--format=tar", "-o", str(archivo), ref, repo=repo)
    destino.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archivo) as paquete:
        paquete.extractall(destino, filter="data")
    archivo.unlink()


def datos_del_proyecto() -> tuple[str, str]:
    """Id del proyecto vinculado y nombre de su entorno de producción: hacen falta para subir desde una
    carpeta temporal, que no está vinculada."""
    estado_json = json.loads(railway("status", "--json").stdout)
    entornos = [e["node"]["name"] for e in estado_json["environments"]["edges"]]
    if not entornos:
        raise RuntimeError("El proyecto de Railway no tiene entornos.")
    return estado_json["id"], "production" if "production" in entornos else entornos[0]


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


def encender(
    servicios: list[Servicio],
    forzar: bool,
    esperar: bool,
    ref: str = REF_POR_DEFECTO,
    local: bool = False,
    subir_carpeta: bool = False,
) -> int:
    if local:
        print(f"Se subirá lo que hay en esta carpeta (rama {rama_actual()}), no lo publicado en GitHub.")
        if hay_cambios_sin_commitear():
            print("AVISO: hay cambios sin commitear; también se publicarán.")
            if not forzar and not confirmar("¿Continuar?"):
                print("Cancelado.")
                return 1
        elif not forzar and not confirmar("¿Encender " + ", ".join(s.nombre for s in servicios) + "?"):
            print("Cancelado.")
            return 1
        proyecto = datos_del_proyecto() if subir_carpeta else None
        return _desplegar(servicios, esperar, carpeta=None, proyecto=proyecto, subir_carpeta=subir_carpeta)

    if ref.startswith("origin/") or ref == "origin":
        print("Actualizando las referencias de GitHub (git fetch)...")
        git("fetch", "origin")
    commit, asunto = resolver_ref(ref)
    print(f"Se desplegará {ref}: {commit} {asunto}")
    if not forzar and not confirmar("¿Encender " + ", ".join(s.nombre for s in servicios) + "?"):
        print("Cancelado.")
        return 1
    proyecto = datos_del_proyecto()
    with tempfile.TemporaryDirectory(prefix="mia-despliegue-") as temporal:
        carpeta = Path(temporal) / "codigo"
        exportar_ref(ref, carpeta)
        return _desplegar(servicios, esperar, carpeta=carpeta, proyecto=proyecto, subir_carpeta=subir_carpeta)


def _desplegar(
    servicios: list[Servicio],
    esperar: bool,
    carpeta: Path | None,
    proyecto: tuple[str, str] | None,
    subir_carpeta: bool = False,
) -> int:
    fallos = 0
    for servicio in servicios:
        anterior = ultimo_despliegue(servicio)
        print(f"\n{servicio.nombre} ({servicio.descripcion}): subiendo...")
        if carpeta is None and not subir_carpeta:
            railway("up", "-s", servicio.nombre, "--detach")
        else:
            proyecto_id, entorno = proyecto
            # Desde la propia carpeta (la temporal, o la del servicio con `subir_carpeta`): `railway up <ruta>` exige
            # que la ruta esté dentro del proyecto vinculado ("prefix not found"), y la temporal no lo está.
            origen = carpeta_de_subida(servicio, carpeta if carpeta is not None else RAIZ_REPO, subir_carpeta)
            railway("up", "-p", proyecto_id, "-e", entorno, "-s", servicio.nombre, "--detach", cwd=origen)
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
    print(f"{'Servicio':<23} {'Último despliegue':<18} {'HTTP':<5} Dirección")
    for servicio in servicios:
        despliegue = ultimo_despliegue(servicio)
        etiqueta = despliegue["status"] if despliegue else "sin despliegues"
        print(f"{servicio.nombre:<23} {etiqueta:<18} {codigo_http(servicio):<5} {servicio.url}")
    print("\nHTTP 200: encendido. 404: apagado. 502: encendido pero mal configurado (puerto).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Enciende, apaga y consulta los servicios de MIA en Railway.")
    parser.add_argument("accion", choices=["estado", "encender", "apagar"])
    parser.add_argument("servicios", nargs="*", help="MIA, mia-whatsapp, mia-computacion, mia-analitica-negocios, mia-panel (por defecto, todos)")
    parser.add_argument("--forzar", action="store_true", help="no pedir confirmación")
    parser.add_argument("--sin-esperar", action="store_true", help="con encender: lanzar los despliegues sin esperar su resultado")
    parser.add_argument(
        "--ref", default=REF_POR_DEFECTO, help=f"con encender: rama o commit publicado que se despliega (por defecto {REF_POR_DEFECTO})"
    )
    parser.add_argument("--local", action="store_true", help="con encender: subir la carpeta local en vez de lo publicado en GitHub")
    parser.add_argument(
        "--config", type=Path, default=ARCHIVO_CONFIG, help="archivo con las direcciones y el modo de subida (por defecto servicios.local.json)"
    )
    args = parser.parse_args()

    if shutil.which("railway") is None:
        print("No se encontró la CLI de Railway. Instalarla con: npm install -g @railway/cli", file=sys.stderr)
        return 2
    try:
        config = cargar_configuracion(args.config)
        elegidos = seleccionar(args.servicios, invertir=args.accion == "apagar", catalogo=aplicar_configuracion(config))
        if args.accion == "estado":
            return estado(elegidos)
        if args.accion == "encender":
            return encender(
                elegidos,
                args.forzar,
                esperar=not args.sin_esperar,
                ref=args.ref,
                local=args.local,
                subir_carpeta=bool(config.get("subir_carpeta", False)),
            )
        return apagar(elegidos, args.forzar)
    except (ValueError, RuntimeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
