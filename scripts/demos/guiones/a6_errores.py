"""A6. Cuando algo falla: errores, reintentos y el tope diario."""

import json
import re

from grabador import Grabacion, responder_json

ID = "a6-errores"
TITULO = "Cuando algo falla"
URL = "http://localhost:3000"
STORAGE = {"mia-consulta-key": "mia_demo_computacion"}


def guion(g: Grabacion) -> None:
    p = g.page
    estado = {"sin_red": False}

    def consulta(route, request):
        modo = json.loads(request.post_data or "{}").get("mode", "literal")
        if estado["sin_red"]:
            route.abort()
        elif modo == "razonamiento":  # el modelo con razonamiento "no está disponible"
            responder_json(route, {"detail": "El proveedor del modelo no respondió."}, 502)
        else:
            route.continue_()  # la respuesta de ejemplo del servidor

    g.simular("**/api/query", consulta)
    p.get_by_role("button", name="Todos", exact=True).wait_for()
    g.pausa(0.8)

    with g.sub("Si se cae tu conexión, la respuesta no llega. Escribe tu pregunta como siempre."):
        estado["sin_red"] = True
        g.escribir(p.get_by_label("Tu pregunta"), "¿Qué se acordó en las actas sobre las becas?")
        g.tecla("Enter")
        p.get_by_text("No se pudo conectar con MIA").wait_for(timeout=15000)
        g.pausa(1.0)

    with g.sub("MIA avisa que no pudo conectarse. Revisa tu conexión y usa «Reintentar» para enviar la misma pregunta."):
        estado["sin_red"] = False
        g.clic(p.get_by_role("button", name="Reintentar", exact=True))
        p.get_by_text("dos becas parciales").first.wait_for(timeout=20000)
        g.pausa(1.2)

    with g.sub("El modo con razonamiento puede fallar si el modelo no está disponible. Cámbiate a ese modo y pregunta."):
        g.clic(p.locator(".mode-button"))
        g.clic(p.get_by_role("option", name=re.compile("Con razonamiento")))
        g.escribir(p.get_by_label("Tu pregunta"), "¿Cuántos créditos tiene el Taller de Ejemplo B?")
        g.tecla("Enter")
        p.get_by_text("El modelo de lenguaje no está disponible").wait_for(timeout=15000)
        g.pausa(1.0)

    with g.sub("Puedes reintentar o, mejor, «Reintentar en modo literal», que responde con lo que dicen los documentos."):
        g.mover(p.get_by_role("button", name="Reintentar", exact=True).last)
        g.pausa(1.0)
        g.clic(p.get_by_role("button", name="Reintentar en modo literal"))
        p.get_by_text("4 créditos").first.wait_for(timeout=20000)
        g.pausa(1.2)

    with g.sub("Quien administra MIA fija un tope de gasto diario para cada Consulta. Al alcanzarlo, no se puede preguntar hasta la medianoche."):
        def config_con_tope(route, request):
            respuesta = route.fetch()
            cuerpo = respuesta.json()
            cuerpo["caps"]["cap_reached"] = True
            responder_json(route, cuerpo)

        g.simular("**/api/config", config_con_tope)
        p.reload()
        p.get_by_text("Se alcanzó el tope diario de gasto").wait_for(timeout=15000)
        g.pausa(1.5)

    with g.sub("El aviso aparece bajo el campo de pregunta y no deja enviar. El tope se reinicia a la medianoche."):
        g.mover(p.get_by_text("Se alcanzó el tope diario de gasto"))
        g.pausa(1.5)
