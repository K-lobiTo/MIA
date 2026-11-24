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

from mia.api.routes.query import Image, QueryResponse, Source
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


# Lo que "dicen los documentos" de ejemplo para cada sección posible de una plantilla (por una palabra de su título).
DATOS_DEL_TALLER = {
    "resumen": "El Taller de Ejemplo A es un curso práctico de tres unidades.",
    "requisito": "Tener el plan de estudios al día.",
    "plan": "3 créditos, en tres unidades: fundamentos, práctica guiada y proyecto final.",
    "fecha": "Se imparte los martes a las 6:00 p. m.",
    "modalidad": "Presencial.",
    "duraci": "Un periodo lectivo y 3 créditos.",
    "programa": "Taller de Ejemplo A.",
    "para qui": "Personas del programa de posgrado.",
}
SIN_DATOS = "Sin información en los documentos."


def _titulos(contenido: str, nombre: str) -> list[str]:
    """Los títulos de las secciones de una plantilla: `Título: indicación` o líneas cortas sin punto (el formato de un .docx)."""
    titulos = []
    lineas = [renglon.strip() for renglon in contenido.splitlines() if renglon.strip()]
    for posicion, linea in enumerate(lineas):
        # La primera línea sin ":" de un .docx es el título del documento, no una sección.
        if linea.lower() == nombre.lower() or (posicion == 0 and ":" not in linea):
            continue
        if ":" in linea:
            titulos.append(linea.split(":", 1)[0].strip())
        elif len(linea) <= 40 and "." not in linea:
            titulos.append(linea)
    return titulos


def _con_plantilla(pregunta: str, nombre: str, contenido: str) -> tuple[str, list[Source], bool]:
    """Una respuesta con las mismas secciones, en el mismo orden y con los mismos títulos que la plantilla. Si la pregunta es del
    Taller de Ejemplo A hay datos; una sección sin datos lo dice, no se inventa ni se omite."""
    del_taller = "taller de ejemplo a" in pregunta.lower()
    partes = []
    for titulo in _titulos(contenido, nombre):
        dato = next((v for k, v in DATOS_DEL_TALLER.items() if k in titulo.lower()), SIN_DATOS) if del_taller else SIN_DATOS
        partes.append(f"**{titulo}**\n{dato}")
    fuentes = (
        [Source(domain="Currículum", document="Programa de curso Taller de Ejemplo A.pdf", excerpt="Créditos: 3. (Documento de ejemplo)")]
        if del_taller
        else []
    )
    return "\n\n".join(partes), fuentes, False


def responder(payload, artifact, session, session_missing: bool = False, user=None, template_out=None, **_) -> QueryResponse:
    """Con la firma de `run_query`: devuelve una respuesta fija y deja la fila del registro de consultas."""
    inicio = time.monotonic()
    time.sleep(4.0 if payload.mode in ("razonamiento", "plantilla") else 2.0)  # lo que se ve en pantalla como "Buscando..."
    # Como la consulta real: el historial solo cuenta si el artefacto tiene memoria.
    historial = payload.history if artifact.context_turns > 0 else None
    if payload.mode == "plantilla":
        # La plantilla se resuelve como en la consulta real: solo las visibles para el artefacto y la persona.
        from mia.templates.service import resolve_template

        plantilla = resolve_template(session, artifact, user, payload.template_id or "")
        if template_out is not None:
            template_out.update(id=plantilla.id, name=plantilla.name)
        texto, fuentes, sin_info = _con_plantilla(payload.question, plantilla.name, plantilla.content)
    else:
        texto, fuentes, sin_info = _respuesta(payload, historial)
    identificador = str(uuid.uuid4())
    session.add(
        QueryLog(
            id=identificador,
            artifact_id=artifact.id,
            question=payload.question,
            domain_ids=json.dumps(list(payload.domains)),
            mode=payload.mode,
            model="modelo-razonamiento-ejemplo" if payload.mode in ("razonamiento", "plantilla") else "modelo-literal-ejemplo",
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


PROGRAMAS = ["Unidad de Postgrados de Computación", "Área académica de Analítica de Negocios"]


def responder_bot(request, artifact, session, clarify=None, extras=None) -> QueryResponse:
    """Con la firma de `run_query` que usa `POST /bot/query`: lo mismo que `responder`, más lo que el bot necesita
    (la aclaración de programa, los programas de las fuentes y las imágenes de los documentos citados). Sin demora."""
    pregunta = request.question
    minuscula = pregunta.lower()
    fuentes: list[Source] = []
    imagenes: list[Image] = []
    programas: list[str] = []
    candidatos: list[str] = []
    sin_info = False
    if "matrícula" in minuscula or "matricula" in minuscula:
        programa = next((p for p in PROGRAMAS if p.split()[-1].lower() in minuscula), None)
        if programa is None:
            sin_info, candidatos = True, list(PROGRAMAS)
            texto = NO_INFO
        else:
            texto = (
                f"## Matrícula\nPara **{programa}**, la matrícula se hace en las fechas del **calendario de ejemplo** "
                "del periodo.\n\n* Se paga en la oficina del programa.\n* Hay que tener el plan de estudios al día."
            )
            fuentes = [
                Source(domain="Promoción", document="Calendario de ejemplo del periodo.txt", excerpt="Matrícula: primera semana. (Documento de ejemplo)")
            ]
            programas = [programa]
    elif "taller de ejemplo a" in minuscula and "crédito" in minuscula:
        texto = "El **Taller de Ejemplo A** tiene **3 créditos** y pide 6 horas de trabajo extraclase por semana."
        fuentes = [
            Source(domain="Currículum", document="Programa de curso Taller de Ejemplo A.pdf", excerpt="Créditos: 3. (Documento de ejemplo)"),
        ]
        imagenes = [Image(url="/media/demo-horario", caption="Horario de las clases", document="Programa de curso Taller de Ejemplo A.pdf")]
        programas = [PROGRAMAS[0]]
    else:
        texto, sin_info = NO_INFO, True
    if extras is not None:
        extras.clarify = candidatos
        extras.programs = programas
    identificador = str(uuid.uuid4())
    session.add(
        QueryLog(
            id=identificador,
            artifact_id=artifact.id,
            question=pregunta,
            domain_ids=json.dumps(list(request.domains)),
            mode="literal",
            model="modelo-literal-ejemplo",
            prompt_tokens=900,
            completion_tokens=120,
            cost_usd=Decimal("0.004"),
            latency_ms=700,
            outcome="no_info" if sin_info else "answered",
            sources=json.dumps([{"domain": f.domain, "document": f.document} for f in fuentes]),
        )
    )
    session.commit()
    return QueryResponse(
        id=identificador, answer=texto, sources=fuentes, mode="literal", latency_ms=700, no_info=sin_info, images=imagenes
    )
