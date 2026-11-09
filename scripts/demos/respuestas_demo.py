"""SOLO DESARROLLO: sustituto de `run_query` para el servidor de demostración.

Reemplaza únicamente la parte que necesita Qdrant y un modelo de lenguaje. Lo demás de `POST /query` es el real: permisos,
sesión, historial guardado, guardado de la conversación y calificaciones (se escribe una fila en el registro de consultas
para que `POST /query/{id}/feedback` funcione y para que Uso la cuente).

Las respuestas son fijas y de ejemplo. El seguimiento ("¿Y cuántos créditos tiene?") se resuelve con el historial que la API
recibe de verdad: sin historial responde "sin información", como la búsqueda real.
"""

import json
import time
import uuid
from decimal import Decimal

from mia.api.routes.query import QueryResponse, Source
from mia.storage.models import QueryLog

CURSOS = {
    "Taller de Ejemplo A": {
        "creditos": 3,
        "horas": 6,
        "contenidos": "tres unidades: fundamentos, práctica guiada y proyecto final",
    },
    "Taller de Ejemplo B": {
        "creditos": 4,
        "horas": 8,
        "contenidos": "cuatro unidades: modelado, simulación, análisis de resultados y proyecto final",
    },
    "Seminario de Ejemplo": {
        "creditos": 2,
        "horas": 4,
        "contenidos": "dos unidades: revisión de literatura y presentación de avances",
    },
}

NO_INFO = (
    "No encontré información suficiente en los documentos para responder esa pregunta. Prueba con otras palabras o "
    "pregunta por otro tema."
)


def _curso_de(texto: str) -> str | None:
    for nombre in CURSOS:
        if nombre.lower() in texto.lower():
            return nombre
    return None


def _respuesta(payload, historial) -> tuple[str, list[Source], bool]:
    pregunta = payload.question
    minuscula = pregunta.lower()
    if "becas" in minuscula:
        return (
            (
                "En el **Acta de ejemplo 02-2026** el Consejo acordó aprobar **dos becas parciales** para el segundo "
                "semestre, una por cada línea de investigación del programa."
            ),
            [Source(domain="Memoria del Consejo", document="Acta de ejemplo 02-2026.pdf", excerpt="ACUERDO 3. El Consejo aprueba dos becas parciales. (Documento de ejemplo)")],
            False,
        )
    if "tesis" in minuscula and "requisito" in minuscula:
        return (
            (
                "La **Guía de tesis de ejemplo** pide una **propuesta aprobada por el Consejo** antes de iniciar el "
                "desarrollo, y un profesor guía asignado."
            ),
            [Source(domain="Proyectos de graduación: Tesis", document="Guía de tesis de ejemplo.docx", excerpt="Requisitos: propuesta aprobada por el Consejo y profesor guía asignado. (Documento de ejemplo)")],
            False,
        )
    tema = next((k for k in ("contenido", "crédito", "hora") if k in minuscula), None)
    if tema:
        curso = _curso_de(pregunta)
        # Un seguimiento sin curso en la pregunta solo se entiende con el historial que llegó a la API.
        if curso is None and historial:
            curso = _curso_de(historial[-1].question) or _curso_de(historial[-1].answer)
        if curso:
            datos = CURSOS[curso]
            frases = {
                "contenido": f"El **{curso}** cubre {datos['contenidos']}.",
                "crédito": f"El **{curso}** tiene **{datos['creditos']} créditos**.",
                "hora": f"El **{curso}** pide **{datos['horas']} horas** de trabajo extraclase por semana.",
            }
            fuente = Source(
                domain="Currículum",
                document=f"Programa de curso {curso}.pdf",
                excerpt=f"{curso}. Créditos: {datos['creditos']}. Horas extraclase por semana: {datos['horas']}. Contenidos: {datos['contenidos']}. (Documento de ejemplo)",
            )
            return frases[tema], [fuente], False
    return NO_INFO, [], True


def responder(payload, artifact, session, session_missing: bool = False) -> QueryResponse:
    """Con la firma de `run_query`: devuelve una respuesta fija y deja la fila del registro de consultas."""
    inicio = time.monotonic()
    time.sleep(4.0 if payload.mode == "razonamiento" else 2.0)  # lo que se ve en pantalla como "Buscando..."
    # Como la consulta real: el historial solo cuenta si el artefacto tiene memoria.
    historial = payload.history if artifact.context_turns > 0 else None
    texto, fuentes, sin_info = _respuesta(payload, historial)
    identificador = str(uuid.uuid4())
    session.add(
        QueryLog(
            id=identificador,
            artifact_id=artifact.id,
            question=payload.question,
            domain_ids=json.dumps(list(payload.domains)),
            mode=payload.mode,
            model="modelo-razonamiento-ejemplo" if payload.mode == "razonamiento" else "modelo-literal-ejemplo",
            prompt_tokens=900,
            completion_tokens=120,
            cost_usd=Decimal("0.004"),
            latency_ms=int((time.monotonic() - inicio) * 1000),
            outcome="no_info" if sin_info else "answered",
            sources=json.dumps([{"domain": f.domain, "document": f.document} for f in fuentes]),
        )
    )
    session.commit()
    return QueryResponse(
        id=identificador,
        answer=texto,
        sources=fuentes,
        mode=payload.mode,
        latency_ms=int((time.monotonic() - inicio) * 1000),
        no_info=sin_info,
    )
