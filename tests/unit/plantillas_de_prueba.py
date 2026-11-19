"""Ayudas de las pruebas del modo plantilla (feature 020): plantillas insertadas directamente en la base y consultas con
`template_id`. Se usan junto con `historial_de_prueba.py` y `chat_de_prueba.py`."""

import uuid

from mia.storage.models import ResponseTemplate
from mia.templates.service import normalize_name

CONTENIDO = "# Resumen\nQué es el programa.\n\n# Requisitos\nLo que se pide para ingresar.\n\n# Costos\nCuánto cuesta."


def plantilla_del_artefacto(db, artifact_id, nombre="Informe de programa", contenido=CONTENIDO) -> str:
    identificador = str(uuid.uuid4())
    with db() as session:
        session.add(
            ResponseTemplate(
                id=identificador, scope="artifact", owner_key=f"a:{artifact_id}", artifact_id=artifact_id,
                name=nombre, name_key=normalize_name(nombre), content=contenido, created_by="prueba",
            )
        )
        session.commit()
    return identificador


def plantilla_personal(db, user_id, nombre="Mi informe", contenido=CONTENIDO, artifact_id=None) -> str:
    identificador = str(uuid.uuid4())
    with db() as session:
        session.add(
            ResponseTemplate(
                id=identificador, scope="personal", owner_key=f"u:{user_id}", artifact_id=artifact_id, user_id=user_id,
                name=nombre, name_key=normalize_name(nombre), content=contenido, created_by=user_id,
            )
        )
        session.commit()
    return identificador


def preguntar_con_plantilla(client, artefacto, pregunta, template_id, *, modo="plantilla", historial=None, headers=None):
    cuerpo = {"domains": ["dom-1"], "question": pregunta, "mode": modo}
    if template_id is not None:
        cuerpo["template_id"] = template_id
    if historial is not None:
        cuerpo["history"] = historial
    return client.post("/query", json=cuerpo, headers={**artefacto.headers, **(headers or {})})
