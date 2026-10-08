"""Pruebas de aceptación del MVP contra una instancia de la API (local o Render).

Corre un conjunto fijo de preguntas contra POST /query y verifica, para cada una, si la API
respondió con contenido citando el documento esperado, o si respondió "sin información" sin
fuentes. Requiere los dominios con los documentos reales descritos en docs/PRUEBAS_MVP.md
(entregados por la Unidad de Posgrado en Computación y la Maestría en Analítica de Negocios).

Uso:
    python scripts/pruebas_mvp.py --url https://mia-api-5qgh.onrender.com
    python scripts/pruebas_mvp.py --url http://localhost:8000 --solo U1,I1

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

AN_CONSEJO = "Analítica de Negocios: Consejo de Área"
AN_CURRICULUM = "Analítica de Negocios: Currículum"
CO_PLANES = "Computación: Planes de estudio"
CO_PROYECTOS = "Computación: Proyectos de graduación"
CO_CONSEJO = "Computación: Consejo de Unidad"

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
    # Texto que debe aparecer en la respuesta (sin distinguir mayúsculas), p. ej. un dato concreto
    # o el último punto de una lista larga, para detectar respuestas incorrectas o cortadas.
    contiene: str = ""


CASOS = [
    # Analítica de Negocios, Consejo de Área: actas de las sesiones 01 a 06 de 2026.
    Caso(
        "A1",
        "¿Qué se discutió sobre becas en caso de superar los 25 estudiantes admitidos?",
        [AN_CONSEJO],
        "respuesta",
        "04-2026",
    ),
    Caso(
        "A2",
        "¿Quién fue designado coordinador específico del proyecto ante FUNDATEC?",
        [AN_CONSEJO],
        "respuesta",
        "01-2026",
        contiene="Martín Solís",
    ),
    Caso(
        "A3",
        "¿Qué se discutió sobre becas y descuentos para funcionarios del TEC?",
        [AN_CONSEJO],
        "respuesta",
        "03-2026",
    ),
    # Analítica de Negocios, Currículum: programas de curso (DOCX con tablas), reglamentos y TFG.
    Caso(
        "U1",
        "¿Cuántas horas extraclase por semana tiene el curso Big Data para Negocios?",
        [AN_CURRICULUM],
        "respuesta",
        "Big Data para Negocios",
        contiene="14",
    ),
    Caso(
        "U2",
        "¿De qué curso es requisito Big Data para Negocios?",
        [AN_CURRICULUM],
        "respuesta",
        "Big Data para Negocios",
        contiene="Big Data",
    ),
    Caso(
        "U3",
        "¿Cada cuánto se abre el proceso de admisión al programa?",
        [AN_CURRICULUM],
        "respuesta",
        "Reglamento del Programa",
        contiene="año",
    ),
    Caso(
        "U4",
        "¿Cuáles son las líneas de TFG de la maestría?",
        [AN_CURRICULUM],
        "respuesta",
        "Líneas de TFG",
        # Última de las seis líneas: exige el documento completo (es corto, ver rag/context.py).
        contiene="Analítica de Texto",
    ),
    # Computación, Planes de estudio: MCC, Ciberseguridad y Gerencia de TI.
    Caso(
        "P1",
        "¿Cuántas horas extraclase por semana tiene el curso Cibercrimen?",
        [CO_PLANES],
        "respuesta",
        "MC3010",
        contiene="14",
    ),
    Caso(
        "P2",
        "¿Cuántos créditos tiene el curso Cibercrimen y en qué área del plan de estudios se ubica?",
        [CO_PLANES],
        "respuesta",
        "MC3010",
        contiene="4",
    ),
    # Computación, Consejo de Unidad: actas de 2025 (contienen datos personales de estudiantes;
    # las preguntas de prueba tratan solo temas académicos).
    Caso(
        "K1",
        "¿Qué se aprobó sobre impartir el curso Deep Learning por tutoría?",
        [CO_CONSEJO],
        "respuesta",
        "CUP_002",
    ),
    Caso(
        "K2",
        "¿Qué se acordó sobre el cambio de nombre de la Maestría en Computación?",
        [CO_CONSEJO],
        "respuesta",
        "06-2025",
    ),
    # Caso de uso 1 del documento conceptual: sin estas actas respondía "sin información".
    Caso(
        "CU1",
        "¿Qué se acordó en el Consejo de Unidad sobre la maestría de Ciberseguridad?",
        [CO_CONSEJO],
        "respuesta",
        "Acta",
    ),
    # Computación, Proyectos de graduación.
    Caso(
        "G1",
        "¿Qué trabajo de graduación trata sobre drones en aeropuertos?",
        [CO_PROYECTOS],
        "respuesta",
        "Drones",
    ),
    Caso(
        "G2",
        "¿Qué compara el análisis de modelos centralizados y descentralizados en sistemas de pagos?",
        [CO_PROYECTOS],
        "respuesta",
        "Luis Alvarado",
    ),
    # Sin respuesta en ningún dominio.
    Caso(
        "N1",
        "¿Cuál es la receta del gallo pinto?",
        [AN_CONSEJO, AN_CURRICULUM, CO_PLANES, CO_PROYECTOS, CO_CONSEJO],
        "sin_informacion",
    ),
    # Multi-dominio con respuesta en uno solo de los dominios.
    Caso(
        "X1",
        "¿Cuántas horas extraclase por semana tiene el curso Cibercrimen?",
        [AN_CURRICULUM, CO_PLANES],
        "respuesta",
        "MC3010",
        contiene="14",
    ),
    # Aislamiento: una pregunta de un dominio no debe responderse consultando otro.
    Caso(
        "I1",
        "¿Cuántas horas extraclase por semana tiene el curso Cibercrimen?",
        [AN_CURRICULUM],
        "sin_informacion",
    ),
    Caso(
        "I3",
        "¿Qué se acordó sobre el cambio de nombre de la Maestría en Computación?",
        [AN_CONSEJO],
        "sin_informacion",
    ),
    Caso(
        "I2",
        "¿Qué se discutió sobre becas en caso de superar los 25 estudiantes admitidos?",
        [CO_PROYECTOS],
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
    if caso.contiene and caso.contiene.lower() not in body["answer"].lower():
        return False, f"la respuesta no menciona '{caso.contiene}' (¿quedó incompleta?)"
    return True, f"fuentes: {fuentes}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", required=True, help="URL base de la API, sin barra final")
    parser.add_argument("--solo", default="", help="ids de casos separados por coma (opcional)")
    args = parser.parse_args()
    base_url = args.url.rstrip("/")
    solo = {c.strip() for c in args.solo.split(",") if c.strip()}

    dominios = _dominios_por_nombre(base_url)
    casos = [c for c in CASOS if not solo or c.id in solo]
    faltantes = {d for c in casos for d in c.dominios} - dominios.keys()
    if faltantes:
        sys.exit(f"Faltan dominios en la instancia: {sorted(faltantes)}")

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
