"""A4. Preguntas de seguimiento: la memoria de la conversación."""

from grabador import Grabacion

ID = "a4-seguimientos"
TITULO = "Preguntas de seguimiento"
URL = "http://localhost:3000"
STORAGE = {"mia-consulta-key": "mia_demo_computacion"}  # el artefacto recuerda las últimas 2 preguntas


def _preguntar(g: Grabacion, texto: str, respuesta: str) -> None:
    p = g.page
    g.escribir(p.get_by_label("Tu pregunta"), texto)
    g.tecla("Enter")
    p.get_by_text(respuesta).first.wait_for(timeout=20000)
    g.pausa(1.2)


def guion(g: Grabacion) -> None:
    p = g.page
    p.get_by_role("button", name="Todos", exact=True).wait_for()
    g.pausa(0.8)

    with g.sub("Esta Consulta recuerda las últimas preguntas de tu conversación. El aviso está bajo el campo de pregunta."):
        g.mover(p.get_by_text("Recuerda las últimas 2 preguntas de esta conversación"))
        g.pausa(1.2)

    with g.sub("Empieza con una pregunta completa, por ejemplo sobre los contenidos de un curso."):
        _preguntar(g, "¿Cuáles son los contenidos del Taller de Ejemplo A?", "tres unidades")

    with g.sub("Ahora pregunta sin repetir el curso: MIA entiende a cuál te refieres por lo que hablaron antes."):
        _preguntar(g, "¿Y cuántos créditos tiene?", "3 créditos")

    with g.sub("Puedes seguir encadenando preguntas sobre el mismo tema."):
        _preguntar(g, "¿Y cuántas horas extraclase?", "6 horas")

    with g.sub("Si cambias de tema, escribe la pregunta completa: lo anterior solo sirve para entender la nueva."):
        g.pausa(2.0)

    with g.sub("Sin iniciar sesión, la conversación vive solo en esta página. Si la recargas, empieza de nuevo."):
        g.pausa(1.0)
        p.reload()
        p.get_by_role("button", name="Todos", exact=True).wait_for()
        g.pausa(1.0)

    with g.sub("Sin la conversación anterior, la misma pregunta no se entiende y MIA responde que no encontró información."):
        g.escribir(p.get_by_label("Tu pregunta"), "¿Y cuántos créditos tiene?")
        g.tecla("Enter")
        p.get_by_text("No encontré información suficiente").first.wait_for(timeout=20000)
        g.pausa(1.5)
