"""Cliente de terminal para consultar la API de MIA.

Muestra los dominios disponibles, permite elegir uno o varios y hacer preguntas en un ciclo.

Uso:
    python scripts/cliente.py                              # usa la API de Render
    python scripts/cliente.py --url http://localhost:8000  # otra instancia
    MIA_API_URL=http://localhost:8000 python scripts/cliente.py

Dentro de la sesión de preguntas:
    :d  cambiar de dominios
    :f  mostrar u ocultar los fragmentos citados
    :s  salir

Solo usa la biblioteca estándar, para poder correrlo sin instalar el proyecto.
"""

import argparse
import json
import os
import sys
import textwrap
import urllib.error
import urllib.request

URL_POR_DEFECTO = "https://mia-api-5qgh.onrender.com"
TIMEOUT = 200
ANCHO = 90


def _request(url: str, payload: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=data, headers={"content-type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        try:
            return error.code, json.load(error)
        except json.JSONDecodeError:
            return error.code, {}


def _envolver(texto: str, sangria: str = "  ") -> str:
    return "\n".join(
        textwrap.fill(parrafo, ANCHO, initial_indent=sangria, subsequent_indent=sangria)
        for parrafo in texto.splitlines()
        if parrafo.strip()
    )


def _listar_dominios(base_url: str) -> list[dict]:
    print("Conectando con la API (si estaba dormida puede tardar hasta un minuto)...")
    try:
        status, dominios = _request(f"{base_url}/domains")
    except (urllib.error.URLError, TimeoutError) as error:
        sys.exit(f"No se pudo conectar con {base_url}: {error}")
    if status != 200:
        sys.exit(f"No se pudieron listar los dominios (HTTP {status})")
    if not dominios:
        sys.exit("La instancia no tiene dominios cargados.")
    return dominios


def _elegir_dominios(dominios: list[dict]) -> list[dict] | None:
    print("\nDominios disponibles:")
    for numero, dominio in enumerate(dominios, start=1):
        descripcion = f" ({dominio['description']})" if dominio["description"] else ""
        print(f"  {numero}. {dominio['name']}{descripcion}")
    print("  t. Todos")
    print("  s. Salir")

    while True:
        opcion = input("\nElige uno o varios (p. ej. 1 o 1,2): ").strip().lower()
        if opcion == "s":
            return None
        if opcion == "t":
            return dominios
        try:
            numeros = {int(parte) for parte in opcion.split(",") if parte.strip()}
        except ValueError:
            numeros = set()
        if numeros and all(1 <= n <= len(dominios) for n in numeros):
            return [dominios[n - 1] for n in sorted(numeros)]
        print(f"Opción no válida: ingresa números entre 1 y {len(dominios)}, 't' o 's'.")


def _mostrar_respuesta(body: dict, con_fragmentos: bool) -> None:
    print("\nRespuesta:")
    print(_envolver(body["answer"]))
    if not body["sources"]:
        return
    print("\nFuentes:")
    documentos = sorted({(s["document"], s["domain"]) for s in body["sources"]})
    for documento, dominio in documentos:
        print(f"  - {documento} ({dominio})")
    if con_fragmentos:
        print("\nFragmentos citados:")
        for numero, fuente in enumerate(body["sources"], start=1):
            extracto = " ".join(fuente["excerpt"].split())
            print(f"  [{numero}] {fuente['document']}")
            print(_envolver(extracto[:400] + ("..." if len(extracto) > 400 else ""), "      "))


def _sesion_de_preguntas(base_url: str, seleccion: list[dict]) -> bool:
    """Devuelve True si el usuario quiere cambiar de dominios, False si quiere salir."""
    nombres = ", ".join(d["name"] for d in seleccion)
    print(f"\nConsultando: {nombres}")
    print("Escribe tu pregunta (:d cambiar dominios, :f mostrar fragmentos, :s salir).")
    con_fragmentos = False

    while True:
        pregunta = input("\n> ").strip()
        if not pregunta:
            continue
        if pregunta == ":s":
            return False
        if pregunta == ":d":
            return True
        if pregunta == ":f":
            con_fragmentos = not con_fragmentos
            print(f"Fragmentos {'visibles' if con_fragmentos else 'ocultos'}.")
            continue

        print("Consultando...")
        try:
            status, body = _request(
                f"{base_url}/query",
                {"domains": [d["id"] for d in seleccion], "question": pregunta},
            )
        except (urllib.error.URLError, TimeoutError) as error:
            print(f"Error de conexión: {error}")
            continue

        if status == 200:
            _mostrar_respuesta(body, con_fragmentos)
        elif status == 502:
            print("El LLM no está disponible en este momento (Gemini saturado). Reintenta en unos segundos.")
        else:
            print(f"Error HTTP {status}: {body.get('detail', body)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--url",
        default=os.environ.get("MIA_API_URL", URL_POR_DEFECTO),
        help=f"URL base de la API (por defecto {URL_POR_DEFECTO} o $MIA_API_URL)",
    )
    base_url = parser.parse_args().url.rstrip("/")

    print(f"MIA: Memoria Institucional Académica ({base_url})")
    dominios = _listar_dominios(base_url)
    try:
        while True:
            seleccion = _elegir_dominios(dominios)
            if seleccion is None or not _sesion_de_preguntas(base_url, seleccion):
                break
    except (KeyboardInterrupt, EOFError):
        print()
    print("Hasta luego.")


if __name__ == "__main__":
    main()
