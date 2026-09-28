"""Pruebas de aceptación del MVP contra una instancia de la API (local o Render).

Corre un conjunto fijo de preguntas contra POST /query y verifica, para cada una, si la API
respondió con contenido citando el documento esperado, o si respondió "sin información" sin
fuentes. Requiere que los dominios "Memoria del Consejo" y "Currículum" existan y tengan cargados
los documentos de prueba descritos en docs/PRUEBAS_MVP.md.

Uso:
    python scripts/pruebas_mvp.py --url https://mia-api-5qgh.onrender.com
    python scripts/pruebas_mvp.py --url http://localhost:8000 --solo C1,CU6

Solo usa la biblioteca estándar, para poder correrlo sin instalar el proyecto.
"""

import argparse
import json
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from dataclasses import dataclass

MEMORIA = "Memoria del Consejo"
CURRICULUM = "Currículum"

NO_INFO_PREFIX = "No encontré información suficiente"

# Reintentos ante 502: el tier gratuito de Gemini se satura con frecuencia (ver docs/OPERACION.md).
REINTENTOS = 3
ESPERA_REINTENTO = 20


@dataclass
class Caso:
    id: str
    pregunta: str
    dominios: list[str]
    # "respuesta": debe responder con fuentes; "sin_informacion": respuesta fija y sin fuentes.
    espera: str
    # Fragmento del nombre de archivo que debe aparecer entre las fuentes (solo para "respuesta").
    documento: str = ""


CASOS = [
    # Memoria del Consejo: actas 3436, 3437 y 3438 del Consejo Institucional del TEC.
    Caso("M1", "¿Cuánto se pagará de dietas a los estudiantes?", [MEMORIA], "respuesta", "3437"),
    Caso("M2", "¿Se aprobó el acta 3435?", [MEMORIA], "respuesta", "3438"),
    Caso("M3", "¿Cómo está conformado el Consejo Institucional?", [MEMORIA], "respuesta", "3437"),
    Caso(
        "M4",
        "¿Qué se aprobó sobre el Plan Táctico Institucional 2026-2028?",
        [MEMORIA],
        "respuesta",
        "3438",
    ),
    Caso("M5", "¿Qué se acordó sobre el programa de inglés?", [MEMORIA], "respuesta", "3438"),
    Caso(
        "M6",
        "¿Cuándo abre la matrícula de la maestría en Computación?",
        [MEMORIA],
        "sin_informacion",
    ),
    Caso("M7", "¿Cuál es la receta del gallo pinto?", [MEMORIA], "sin_informacion"),
    # Currículum: programas de curso de la Maestría en Computación.
    Caso(
        "C1",
        "¿Cómo se evalúa el curso Análisis y Diseño de Algoritmos?",
        [CURRICULUM],
        "respuesta",
        "MC6102",
    ),
    Caso(
        "C2",
        "¿Qué requisitos tiene el curso Diseño de Experimentos?",
        [CURRICULUM],
        "respuesta",
        "MC6104",
    ),
    Caso(
        "C3",
        "¿De qué curso es requisito Sistemas Operativos Avanzados?",
        [CURRICULUM],
        "respuesta",
        "MC6004",
    ),
    Caso(
        "C4",
        "¿Cuántos créditos tiene el curso Introducción a la Investigación?",
        [CURRICULUM],
        "respuesta",
        "MC7201",
    ),
    # Casos de uso 1 y 6 del documento conceptual.
    Caso(
        "CU1",
        "¿Qué se acordó en el Consejo de Unidad sobre la maestría de Ciberseguridad en los "
        "últimos dos años?",
        [MEMORIA],
        "sin_informacion",
    ),
    # Con los datos de prueba, CU1 y CU6 no tienen respuesta: las actas son del Consejo
    # Institucional (no del Consejo de Unidad) y los programas de curso describen el estado vigente
    # sin historial de cambios. Cuando se carguen esos documentos, cambiar a "respuesta".
    Caso(
        "CU6",
        "¿Qué cambios se le han hecho al programa de la maestría en Ciencia de la Computación "
        "y cuándo?",
        [CURRICULUM, MEMORIA],
        "sin_informacion",
    ),
    # Consultas multi-dominio con respuesta en uno solo de los dominios.
    Caso(
        "X1",
        "¿Cómo se evalúa el curso Análisis y Diseño de Algoritmos?",
        [CURRICULUM, MEMORIA],
        "respuesta",
        "MC6102",
    ),
    Caso(
        "X2",
        "¿Desde cuándo está vigente el programa del curso Diseño de Experimentos?",
        [CURRICULUM, MEMORIA],
        "respuesta",
        "MC6104",
    ),
    # Aislamiento: una pregunta de un dominio no debe responderse consultando el otro.
    Caso(
        "A1",
        "¿Cómo se evalúa el curso Análisis y Diseño de Algoritmos?",
        [MEMORIA],
        "sin_informacion",
    ),
    Caso(
        "A2",
        "¿Qué se acordó sobre el programa de inglés?",
        [CURRICULUM],
        "sin_informacion",
    ),
]


def _normalizar(texto: str) -> str:
    # Los nombres de archivo con tildes pueden venir en NFD según el sistema que los subió.
    return unicodedata.normalize("NFC", texto)


def _request(url: str, payload: dict | None = None, timeout: int = 200) -> tuple[int, dict]:
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=data, headers={"content-type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        try:
            return error.code, json.load(error)
        except json.JSONDecodeError:
            return error.code, {}


def _dominios_por_nombre(base_url: str) -> dict[str, str]:
    status, dominios = _request(f"{base_url}/domains")
    if status != 200:
        sys.exit(f"No se pudo listar dominios (HTTP {status})")
    return {_normalizar(d["name"]): d["id"] for d in dominios}


def _consultar(base_url: str, pregunta: str, domain_ids: list[str]) -> tuple[int, dict]:
    for intento in range(1, REINTENTOS + 1):
        status, body = _request(f"{base_url}/query", {"domains": domain_ids, "question": pregunta})
        if status != 502 or intento == REINTENTOS:
            return status, body
        time.sleep(ESPERA_REINTENTO)
    raise AssertionError("inalcanzable")


def _evaluar(caso: Caso, status: int, body: dict) -> tuple[bool, str]:
    if status != 200:
        return False, f"HTTP {status}: {body.get('detail', body)}"
    fuentes = sorted({_normalizar(s["document"]) for s in body["sources"]})
    sin_info = body["answer"].startswith(NO_INFO_PREFIX)
    if caso.espera == "sin_informacion":
        if sin_info and not fuentes:
            return True, "sin información, sin fuentes"
        return False, f"se esperaba 'sin información' y respondió con fuentes {fuentes}"
    if sin_info:
        return False, "se esperaba una respuesta y devolvió 'sin información'"
    if caso.documento and not any(caso.documento in f for f in fuentes):
        return False, f"no cita un documento con '{caso.documento}' (fuentes: {fuentes})"
    return True, f"fuentes: {fuentes}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", required=True, help="URL base de la API, sin barra final")
    parser.add_argument("--solo", default="", help="ids de casos separados por coma (opcional)")
    args = parser.parse_args()
    base_url = args.url.rstrip("/")
    solo = {c.strip() for c in args.solo.split(",") if c.strip()}

    dominios = _dominios_por_nombre(base_url)
    faltantes = {MEMORIA, CURRICULUM} - dominios.keys()
    if faltantes:
        sys.exit(f"Faltan dominios en la instancia: {sorted(faltantes)}")

    casos = [c for c in CASOS if not solo or c.id in solo]
    fallidos = []
    for caso in casos:
        status, body = _consultar(base_url, caso.pregunta, [dominios[d] for d in caso.dominios])
        ok, detalle = _evaluar(caso, status, body)
        print(f"[{'OK   ' if ok else 'FALLA'}] {caso.id:<4} {caso.pregunta}")
        print(f"        dominios: {', '.join(caso.dominios)} | {detalle}")
        if status == 200 and not body["answer"].startswith(NO_INFO_PREFIX):
            print(f"        respuesta: {' '.join(body['answer'].split())[:220]}")
        if not ok:
            fallidos.append(caso.id)

    print(f"\n{len(casos) - len(fallidos)} de {len(casos)} casos correctos", end="")
    print(f" (fallaron: {', '.join(fallidos)})" if fallidos else "")
    return 1 if fallidos else 0


if __name__ == "__main__":
    sys.exit(main())
