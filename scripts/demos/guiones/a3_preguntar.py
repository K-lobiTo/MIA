"""A3. Preguntar y leer la respuesta (Consulta administrativa)."""

import re

from grabador import Grabacion, responder_json

ID = "a3-preguntar"
TITULO = "Preguntar y leer la respuesta"
URL = "http://localhost:3000"
STORAGE = {"mia-consulta-key": "mia_demo_computacion"}  # ya entró con su clave (video A1)

FRAGMENTO_02 = (
    "ACUERDO 3. El Consejo aprueba otorgar dos becas parciales para el segundo semestre de 2026, una por cada línea de "
    "investigación del programa, con base en el promedio y la carta de motivación de las personas solicitantes. "
    "La Coordinación publicará el resultado en la plataforma del programa y comunicará a las personas beneficiadas. "
    "(Documento de ejemplo)"
)
FRAGMENTO_03 = (
    "ACUERDO 1. Las solicitudes de beca se reciben hasta la segunda semana del periodo lectivo. Las solicitudes "
    "presentadas después de esa fecha se atenderán en el periodo siguiente. (Documento de ejemplo)"
)

PREGUNTA_RAZONAMIENTO = "¿Cuántos créditos suman el Taller de Ejemplo A y el Taller de Ejemplo B, y cuál tiene más horas?"
PREGUNTA_SIN_INFO = "¿Cuál es el menú de la cafetería?"


def contenido(cuerpo: dict, n: int) -> tuple[float, dict]:
    """Respuesta fija de POST /query (demora que se ve en pantalla y cuerpo): la interfaz y el resto de la API son reales."""
    pregunta, modo = cuerpo.get("question", ""), cuerpo.get("mode", "literal")
    base = {"id": f"consulta-demo-{n}", "mode": modo, "no_info": False}
    if "becas" in pregunta:
        return 2.5, {**base, "latency_ms": 2300, "answer": (
            "En el **Acta de ejemplo 02-2026** el Consejo acordó aprobar **dos becas parciales** para el segundo "
            "semestre, una por cada línea de investigación del programa.\n\nEl **Acta de ejemplo 03-2026** agrega que "
            "las solicitudes se reciben hasta la segunda semana del periodo."),
            "sources": [
                {"domain": "Memoria del Consejo", "document": "Acta de ejemplo 02-2026.pdf", "excerpt": FRAGMENTO_02},
                {"domain": "Memoria del Consejo", "document": "Acta de ejemplo 03-2026.pdf", "excerpt": FRAGMENTO_03},
            ]}
    if "Taller de Ejemplo" in pregunta:
        return 5.0, {**base, "latency_ms": 19400, "answer": (
            "**Lo que dicen los documentos**\n* El Taller de Ejemplo A tiene **3 créditos** y 6 horas de trabajo "
            "extraclase por semana.\n* El Taller de Ejemplo B tiene **4 créditos** y 8 horas de trabajo extraclase por "
            "semana.\n\n**Conclusión**\nEn total suman **7 créditos**. El Taller de Ejemplo B tiene más horas (8 frente a 6)."),
            "sources": [
                {"domain": "Currículum", "document": "Programa de curso Taller de Ejemplo A.pdf",
                 "excerpt": "Créditos: 3. Horas de trabajo extraclase por semana: 6. (Documento de ejemplo)"},
                {"domain": "Currículum", "document": "Programa de curso Taller de Ejemplo B.pdf",
                 "excerpt": "Créditos: 4. Horas de trabajo extraclase por semana: 8. (Documento de ejemplo)"},
            ]}
    return 2.0, {**base, "latency_ms": 1800, "no_info": True, "sources": [], "answer": (
        "No encontré información suficiente en los documentos para responder esa pregunta. Prueba con otras "
        "palabras o pregunta por otro tema.")}


def guion(g: Grabacion) -> None:
    p = g.page
    g.retener_consultas("**/api/query")
    g.simular("**/api/query/*/feedback", lambda route, request: responder_json(route, {"ok": True}))
    p.get_by_role("button", name="Todos", exact=True).wait_for()
    g.pausa(1.0)

    with g.sub("Antes de preguntar, elige los dominios donde quieres buscar (se explica en el video anterior)."):
        g.clic(p.get_by_role("button", name="Todos", exact=True))

    with g.sub("Toca un ejemplo para escribirlo en el campo, o escribe tu propia pregunta."):
        g.clic(p.get_by_role("button", name="¿Qué se acordó en las actas sobre las becas?"))

    with g.sub("Pulsa Preguntar o presiona Enter. Mayúsculas más Enter agrega una línea."):
        g.clic(p.get_by_role("button", name="Preguntar", exact=True))
        g.responder_consulta(contenido)
        p.get_by_text("Fuentes", exact=True).wait_for(timeout=15000)

    with g.sub("MIA responde solo con lo que dicen los documentos. Abajo ves el modo y el tiempo que tardó."):
        g.pausa(1.0)

    with g.sub("Las fuentes son los documentos de donde sale la respuesta, con su dominio entre paréntesis."):
        g.mover(p.get_by_text("Fuentes", exact=True))
        g.pausa(0.8)

    with g.sub("«Ver fragmentos» muestra el texto exacto en que se apoya la respuesta. «Ver más» lo amplía."):
        g.clic(p.get_by_text(re.compile(r"Ver fragmentos")))
        g.pausa(0.8)
        g.clic(p.get_by_role("button", name="Ver más").first)

    with g.sub("El botón de copiar guarda la respuesta en tu portapapeles."):
        g.clic(p.get_by_label("Copiar respuesta").last)
        g.pausa(0.6)

    with g.sub("Califica la respuesta con Útil o No útil. Después puedes dejar un comentario."):
        g.clic(p.get_by_role("button", name="Útil", exact=True))
        g.escribir(p.get_by_label("Comentario (opcional)"), "Justo lo que necesitaba.")
        g.clic(p.get_by_role("button", name="Enviar comentario"))
        g.pausa(0.8)

    with g.sub("Si el selector de modo aparece, elige «Con razonamiento» para comparar o calcular con varios documentos."):
        g.clic(p.locator(".mode-button"))
        g.pausa(0.8)
        g.clic(p.get_by_role("option", name=re.compile("Con razonamiento")))

    with g.sub("Escribe tu pregunta. Este modo puede tardar más; la pantalla te avisa mientras trabaja."):
        g.escribir(p.get_by_label("Tu pregunta"), PREGUNTA_RAZONAMIENTO)
        g.tecla("Enter")
        g.responder_consulta(contenido)
        p.get_by_text("Conclusión", exact=True).wait_for(timeout=15000)

    with g.sub("La respuesta separa lo que dicen los documentos de la conclusión."):
        g.pausa(1.0)

    with g.sub("Si los documentos no tienen la respuesta, MIA lo dice. Prueba con otras palabras o con otro tema."):
        g.clic(p.locator(".mode-button"))
        g.clic(p.get_by_role("option", name=re.compile("Literal")))
        g.escribir(p.get_by_label("Tu pregunta"), PREGUNTA_SIN_INFO)
        g.tecla("Enter")
        g.responder_consulta(contenido)
        p.get_by_text("No encontré información suficiente").wait_for(timeout=15000)
        g.pausa(1.0)
