#!/usr/bin/env python3
"""Crea los cinco servicios de MIA en una cuenta de Railway, con sus dominios y variables.

Pensado para montar MIA en otra cuenta de Railway (ver "Mudar MIA a otra cuenta de Railway" en
docs/OPERACION.md). Hace con la CLI lo que de otro modo se haría a mano en la interfaz:

  1. (opcional) crea el proyecto: `railway init`.
  2. crea los servicios que falten (vacíos, sin GitHub): MIA, mia-whatsapp, mia-computacion,
     mia-analitica-negocios y mia-panel.
  3. genera el dominio de cada uno (los sitios, apuntando al puerto 3000).
  4. pone las variables, con las direcciones reales: VITE_API_URL de los sitios, MIA_API_URL del bot y
     CORS_ORIGINS de la API. Usa `--skip-deploys`: nada se despliega todavía.
  5. escribe `servicios.local.json` (direcciones de la cuenta nueva y subida por carpeta), que
     `scripts/servicios.py` lee solo, y `.env.railway.generado` con los secretos que se generaron.

Después se despliega con `python scripts/servicios.py encender`.

Lo que NO hace (queda a mano): iniciar sesión (`railway login`) y el límite de uso del espacio de trabajo
(*Usage limits*, solo en la interfaz de Railway).

Uso:
    railway login                                   # con la cuenta nueva
    python scripts/crear_servicios.py --proyecto mia --env-api .env.railway-api --env-bot .env.railway-bot --simular
    python scripts/crear_servicios.py --proyecto mia --env-api .env.railway-api --env-bot .env.railway-bot

`--env-api` es un archivo con las credenciales de la API (DATABASE_URL, QDRANT_URL, QDRANT_API_KEY,
OPENROUTER_API_KEY; lo demás sale de `deploy/railway/variables.example.env`, incluido el modelo de cada modo,
LLM_MODEL_LITERAL y LLM_MODEL_RAZONAMIENTO, que se pueden cambiar en este archivo). `--env-bot`,
con KAPSO_API_KEY. ADMIN_KEY, BOT_SERVICE_KEY y KAPSO_WEBHOOK_SECRET se generan si no vienen en los archivos.
No pasar `.env.produccion` si apunta a las bases de la cuenta anterior.

Se puede repetir sin riesgo: reutiliza los servicios y dominios que ya existen y los secretos ya generados.
`--simular` muestra todo lo que haría sin ejecutar nada. Solo usa la biblioteca estándar.
"""

import argparse
import json
import re
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import servicios as srv

RAIZ_REPO = srv.RAIZ_REPO
PLANTILLA_API = RAIZ_REPO / "deploy" / "railway" / "variables.example.env"
ARCHIVO_SECRETOS = RAIZ_REPO / ".env.railway.generado"
PUERTO_SITIO = "3000"
SITIOS = ("mia-computacion", "mia-analitica-negocios", "mia-panel")
SECRETOS_GENERABLES_API = ("ADMIN_KEY", "BOT_SERVICE_KEY")
# Sin estas, la API no arranca o no puede responder.
OBLIGATORIAS_API = ("DATABASE_URL", "QDRANT_URL", "QDRANT_API_KEY", "OPENROUTER_API_KEY")
OBLIGATORIAS_BOT = ("KAPSO_API_KEY",)
PATRON_DOMINIO = re.compile(r"[A-Za-z0-9][A-Za-z0-9.-]*\.up\.railway\.app")


# ---------------------------------------------------------------------------------------------------------
# Lógica pura (con pruebas en tests/unit/test_crear_servicios.py)
# ---------------------------------------------------------------------------------------------------------


def leer_env(ruta: Path) -> dict[str, str]:
    """Pares CLAVE=valor de un archivo .env (sin comentarios ni comillas externas). Los vacíos se omiten."""
    valores: dict[str, str] = {}
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, _, valor = linea.partition("=")
        valor = valor.strip()
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
            valor = valor[1:-1]
        if valor:
            valores[clave.strip()] = valor
    return valores


def es_secreta(clave: str) -> bool:
    """Las variables que no deben pasar por la línea de comandos (se ven en la lista de procesos)."""
    partes = clave.split("_")
    return clave in {"DATABASE_URL", "QDRANT_URL"} or bool({"KEY", "SECRET", "TOKEN"} & set(partes)) or partes[-1] == "PASSWORD"


def es_marcador(valor: str) -> bool:
    """Valores de ejemplo de la plantilla que no se deben copiar tal cual."""
    return "<" in valor or "usuario:clave" in valor


def extraer_dominio(texto: str) -> str | None:
    """La dirección `https://....up.railway.app` que aparezca en la salida de `railway domain` o `service list`."""
    encontrado = PATRON_DOMINIO.search(texto)
    return f"https://{encontrado.group(0)}" if encontrado else None


def generar_secretos(env_api: dict[str, str], env_bot: dict[str, str], previos: dict[str, str]) -> dict[str, str]:
    """Secretos que faltan: se reutilizan los ya generados (para no rotarlos al repetir) y si no, se crean.

    ADMIN_KEY se mira en el archivo de la API, KAPSO_WEBHOOK_SECRET en el del bot y BOT_SERVICE_KEY en cualquiera
    de los dos (es el mismo valor en la API y en el bot)."""
    dados = {
        "ADMIN_KEY": "ADMIN_KEY" in env_api,
        "BOT_SERVICE_KEY": "BOT_SERVICE_KEY" in env_api or "BOT_SERVICE_KEY" in env_bot,
        "KAPSO_WEBHOOK_SECRET": "KAPSO_WEBHOOK_SECRET" in env_bot,
    }
    return {clave: previos.get(clave) or secrets.token_urlsafe(32) for clave, ya_dado in dados.items() if not ya_dado}


def variables_api(plantilla: dict[str, str], env_api: dict[str, str], urls: dict[str, str], generados: dict[str, str]) -> dict[str, str]:
    """Variables del servicio MIA: la plantilla (sin marcadores), encima lo que da el usuario, encima lo calculado."""
    variables = {k: v for k, v in plantilla.items() if not es_marcador(v)}
    variables.update(env_api)
    for clave in SECRETOS_GENERABLES_API:
        if clave in generados:
            variables[clave] = generados[clave]
    variables["CORS_ORIGINS"] = ",".join(urls[nombre] for nombre in SITIOS)
    return variables


def variables_bot(env_bot: dict[str, str], url_api: str, bot_service_key: str, generados: dict[str, str]) -> dict[str, str]:
    variables = dict(env_bot)
    variables["MIA_API_URL"] = url_api
    variables["BOT_SERVICE_KEY"] = bot_service_key
    if "KAPSO_WEBHOOK_SECRET" in generados:
        variables["KAPSO_WEBHOOK_SECRET"] = generados["KAPSO_WEBHOOK_SECRET"]
    return variables


def variables_sitio(url_api: str) -> dict[str, str]:
    return {"VITE_API_URL": url_api, "PORT": PUERTO_SITIO}


def faltantes(variables: dict[str, str], obligatorias: tuple[str, ...]) -> list[str]:
    return [clave for clave in obligatorias if not variables.get(clave)]


def modos_sin_modelo(variables: dict[str, str]) -> list[str]:
    """Modos que usarían OpenRouter sin modelo propio (LLM_MODEL_*) ni OPENROUTER_MODEL, que es solo el respaldo."""
    proveedores = {
        "LITERAL": variables.get("LLM_PROVIDER_LITERAL") or variables.get("LLM_PROVIDER"),
        "RAZONAMIENTO": variables.get("LLM_PROVIDER_RAZONAMIENTO"),
    }
    return [
        f"LLM_MODEL_{modo}"
        for modo, proveedor in proveedores.items()
        if proveedor == "openrouter" and not (variables.get(f"LLM_MODEL_{modo}") or variables.get("OPENROUTER_MODEL"))
    ]


def avisos_api(variables: dict[str, str]) -> list[str]:
    avisos = []
    if "-pooler" in variables.get("DATABASE_URL", ""):
        avisos.append("DATABASE_URL usa el pooler de Neon; para la API se recomienda la conexión directa (sin '-pooler').")
    return avisos


# ---------------------------------------------------------------------------------------------------------
# Ejecución
# ---------------------------------------------------------------------------------------------------------


class Ejecutor:
    """Corre los comandos de Railway, o solo los muestra con `--simular`."""

    def __init__(self, simular: bool) -> None:
        self.simular = simular

    def correr(self, *args: str, entrada: str | None = None, cambia: bool = True) -> str:
        """Ejecuta `railway <args>` y devuelve su salida. Con simular, los comandos que cambian algo no se ejecutan."""
        if self.simular and cambia:
            print(f"  [simulado] railway {' '.join(args)}" + ("  (valor por stdin)" if entrada is not None else ""))
            return ""
        resultado = subprocess.run(
            ["railway", *args], input=entrada, capture_output=True, text=True, cwd=RAIZ_REPO, check=False
        )
        if resultado.returncode != 0:
            detalle = (resultado.stderr or resultado.stdout).strip().splitlines()
            raise RuntimeError(f"railway {' '.join(args)} falló: {detalle[-1] if detalle else 'sin detalle'}")
        return resultado.stdout


def poner_variables(ejecutor: Ejecutor, servicio: str, variables: dict[str, str]) -> None:
    """Las no secretas en un solo comando; cada secreta por stdin, para que no aparezca en la línea de comandos."""
    abiertas = [f"{k}={v}" for k, v in variables.items() if not es_secreta(k)]
    if abiertas:
        ejecutor.correr("variable", "set", *abiertas, "-s", servicio, "--skip-deploys")
    for clave, valor in variables.items():
        if es_secreta(clave):
            ejecutor.correr("variable", "set", clave, "--stdin", "-s", servicio, "--skip-deploys", entrada=valor)
    print(f"  {servicio}: {len(variables)} variables ({len(variables) - len(abiertas)} secretas por stdin).")


def asegurar_dominio(ejecutor: Ejecutor, servicio: str) -> str:
    """La dirección pública del servicio: la que ya tenga, o una generada (los sitios, al puerto 3000)."""
    existente = ejecutor.correr("domain", "list", "-s", servicio, "--json", cambia=False) if not ejecutor.simular else ""
    url = extraer_dominio(existente)
    if url:
        print(f"  {servicio}: ya tiene dominio, {url}")
        return url
    comando = ["domain", "-s", servicio, "--json"]
    if servicio in SITIOS:
        comando += ["--port", PUERTO_SITIO]
    salida = ejecutor.correr(*comando)
    url = extraer_dominio(salida)
    if ejecutor.simular:
        return f"https://{servicio.lower()}.up.railway.app"
    if not url:
        raise RuntimeError(f"No se pudo leer el dominio generado para {servicio}. Salida: {salida.strip()[:200]}")
    print(f"  {servicio}: dominio {url}")
    return url


def servicios_existentes(ejecutor: Ejecutor) -> set[str]:
    if ejecutor.simular:
        return set()
    try:
        return {s["name"] for s in json.loads(ejecutor.correr("service", "list", "--json", cambia=False))}
    except (json.JSONDecodeError, KeyError, TypeError):
        return set()


def preparar_proyecto(ejecutor: Ejecutor, proyecto: str | None, espacio: str | None) -> None:
    if proyecto:
        comando = ["init", "--name", proyecto, "--json"]
        if espacio:
            comando += ["--workspace", espacio]
        ejecutor.correr(*comando)
        return
    if ejecutor.simular:
        return
    try:
        estado = json.loads(ejecutor.correr("status", "--json", cambia=False))
    except (json.JSONDecodeError, RuntimeError) as error:
        raise RuntimeError("Esta carpeta no está vinculada a un proyecto de Railway: usar --proyecto NOMBRE para crear uno.") from error
    print(f"Proyecto vinculado: {estado.get('name')}")


def guardar_configuracion(urls: dict[str, str], simular: bool) -> None:
    config = {"urls": urls, "subir_carpeta": True}
    if simular:
        print(f"  [simulado] escribiría {srv.ARCHIVO_CONFIG.name}: {json.dumps(config)}")
        return
    if srv.ARCHIVO_CONFIG.exists():
        srv.ARCHIVO_CONFIG.replace(srv.ARCHIVO_CONFIG.with_suffix(".json.bak"))
        print(f"  Había un {srv.ARCHIVO_CONFIG.name}: quedó como {srv.ARCHIVO_CONFIG.name}.bak")
    srv.ARCHIVO_CONFIG.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"  Escrito {srv.ARCHIVO_CONFIG.name} (direcciones de esta cuenta y subida por carpeta).")


def guardar_secretos(generados: dict[str, str], simular: bool) -> None:
    if not generados:
        return
    if simular:
        print(f"  [simulado] guardaría {', '.join(generados)} en {ARCHIVO_SECRETOS.name}")
        return
    contenido = "# Secretos generados por scripts/crear_servicios.py. No versionar.\n" + "".join(f"{k}={v}\n" for k, v in generados.items())
    ARCHIVO_SECRETOS.write_text(contenido, encoding="utf-8")
    ARCHIVO_SECRETOS.chmod(0o600)
    print(f"  Secretos generados ({', '.join(generados)}) guardados en {ARCHIVO_SECRETOS.name}.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Crea los servicios de MIA en una cuenta de Railway.")
    parser.add_argument("--proyecto", help="nombre del proyecto nuevo (railway init); sin él se usa el proyecto ya vinculado")
    parser.add_argument("--espacio", help="espacio de trabajo (ID o nombre) donde crear el proyecto")
    parser.add_argument("--env-api", type=Path, help="archivo .env con las credenciales de la API")
    parser.add_argument("--env-bot", type=Path, help="archivo .env con KAPSO_API_KEY (y lo que se quiera fijar del bot)")
    parser.add_argument("--simular", action="store_true", help="mostrar lo que se haría sin ejecutar nada")
    parser.add_argument("--forzar", action="store_true", help="no pedir confirmación")
    args = parser.parse_args()

    if shutil.which("railway") is None and not args.simular:
        print("No se encontró la CLI de Railway. Instalarla con: npm install -g @railway/cli", file=sys.stderr)
        return 2
    try:
        return ejecutar(args)
    except (ValueError, RuntimeError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2


def ejecutar(args: argparse.Namespace) -> int:
    ejecutor = Ejecutor(args.simular)
    env_api = leer_env(args.env_api) if args.env_api else {}
    env_bot = leer_env(args.env_bot) if args.env_bot else {}
    plantilla = leer_env(PLANTILLA_API)
    previos = leer_env(ARCHIVO_SECRETOS) if ARCHIVO_SECRETOS.exists() else {}

    efectivas = {**{k: v for k, v in plantilla.items() if not es_marcador(v)}, **env_api}
    sin_api = faltantes(env_api, OBLIGATORIAS_API) + modos_sin_modelo(efectivas)
    if sin_api:
        mensaje = f"Faltan en --env-api: {', '.join(sin_api)}."
        if not args.simular:
            raise ValueError(mensaje + " Sin ellas la API no arranca.")
        print(f"AVISO (simulación): {mensaje}")
    for aviso in avisos_api(env_api):
        print(f"AVISO: {aviso}")
    if faltantes(env_bot, OBLIGATORIAS_BOT):
        print("AVISO: falta KAPSO_API_KEY (--env-bot): mia-whatsapp no arrancará hasta ponerla "
              "(railway variable set KAPSO_API_KEY --stdin -s mia-whatsapp).")

    if not args.simular:
        print("Cuenta de Railway en uso:")
        print("  " + ejecutor.correr("whoami", cambia=False).strip())
        if not args.forzar and not srv.confirmar("¿Crear los servicios en esa cuenta?"):
            print("Cancelado.")
            return 1

    print("\n1. Proyecto")
    preparar_proyecto(ejecutor, args.proyecto, args.espacio)

    print("\n2. Servicios")
    existentes = servicios_existentes(ejecutor)
    for servicio in srv.SERVICIOS:
        if servicio.nombre in existentes:
            print(f"  {servicio.nombre}: ya existe.")
        else:
            ejecutor.correr("add", "--service", servicio.nombre)
            print(f"  {servicio.nombre}: creado.")

    print("\n3. Dominios")
    urls = {servicio.nombre: asegurar_dominio(ejecutor, servicio.nombre) for servicio in srv.SERVICIOS}

    print("\n4. Variables (sin desplegar)")
    generados = generar_secretos(env_api, env_bot, previos)
    bot_service_key = env_api.get("BOT_SERVICE_KEY") or env_bot.get("BOT_SERVICE_KEY") or generados["BOT_SERVICE_KEY"]
    api = variables_api(plantilla, env_api, urls, generados)
    api["BOT_SERVICE_KEY"] = bot_service_key
    poner_variables(ejecutor, "MIA", api)
    poner_variables(ejecutor, "mia-whatsapp", variables_bot(env_bot, urls["MIA"], bot_service_key, generados))
    for sitio in SITIOS:
        poner_variables(ejecutor, sitio, variables_sitio(urls["MIA"]))

    print("\n5. Archivos locales")
    guardar_configuracion(urls, args.simular)
    guardar_secretos(generados, args.simular)

    print("\nListo. Falta, a mano: el límite de uso del espacio de trabajo (Usage limits, en la interfaz de Railway).")
    print("Siguiente: python scripts/servicios.py encender   (despliega origin/main; ver 'Desplegar cambios')")
    print(f"Webhook de Kapso: {urls['mia-whatsapp']}/webhooks/kapso")
    print("Direcciones: " + ", ".join(f"{n}={u}" for n, u in urls.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
