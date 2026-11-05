"""Ayudas de las pruebas del historial de chats (feature 015): usuarios con sesión y consultas con y sin ella. Se usan junto
con el mundo simulado de `historial_de_prueba.py`."""

import uuid

from mia.chat import passwords, sessions
from mia.storage.models import ConsultaUser, Conversation, ConversationTurn, _now

CLAVE_DE_PRUEBA = "una-clave-larga-123"
PREGUNTA = "¿Cuándo empiezan las lecciones de analítica?"
SIN_RESPUESTA = "¿Cuánto cuesta la luna?"  # el almacén simulado no encuentra nada: respuesta de "sin información"


def crear_usuario(db, nombre="ana", activo=True) -> str:
    uid = str(uuid.uuid4())
    with db() as session:
        session.add(
            ConsultaUser(
                id=uid,
                username=nombre,
                password_hash=passwords.hash_password(CLAVE_DE_PRUEBA),
                active=activo,
                created_by="prueba",
            )
        )
        session.commit()
    return uid


def iniciar_sesion(db, nombre="ana") -> dict:
    """Crea el usuario (si hace falta) y una sesión; devuelve {"uid", "token", "headers"} listo para las consultas."""
    with db() as session:
        usuario = session.query(ConsultaUser).filter_by(username=nombre).first()
    uid = usuario.id if usuario else crear_usuario(db, nombre)
    with db() as session:
        token, _ = sessions.create_session(session, session.get(ConsultaUser, uid))
    return {"uid": uid, "token": token, "headers": {"X-Session-Token": token}}


def preguntar_con_sesion(
    client,
    artefacto,
    sesion,
    pregunta=PREGUNTA,
    *,
    conversacion=None,
    modo="literal",
    historial=None,
):
    cuerpo = {"domains": ["dom-1"], "question": pregunta, "mode": modo}
    if conversacion is not None:
        cuerpo["conversation_id"] = conversacion
    if historial is not None:
        cuerpo["history"] = historial
    return client.post("/query", json=cuerpo, headers={**artefacto.headers, **sesion["headers"]})


def sembrar_conversacion(db, uid, vueltas=2, titulo="Conversación sembrada", hace_dias=0, textos=None) -> str:
    """Inserta una conversación con `vueltas` vueltas directamente en la base (sin pasar por la consulta). `textos` es una
    lista opcional de (pregunta, respuesta, modo, no_info) que reemplaza las vueltas genéricas."""
    from datetime import timedelta

    cid = str(uuid.uuid4())
    momento = _now() - timedelta(days=hace_dias)
    with db() as session:
        session.add(
            Conversation(id=cid, user_id=uid, title=titulo, created_at=momento, updated_at=momento)
        )
        session.flush()
        generadas = textos or [(f"pregunta {n}", f"respuesta {n}", "literal", False) for n in range(1, vueltas + 1)]
        for n, (pregunta, respuesta, modo, sin_info) in enumerate(generadas, start=1):
            session.add(
                ConversationTurn(
                    id=str(uuid.uuid4()),
                    conversation_id=cid,
                    position=n,
                    question=pregunta,
                    answer=respuesta,
                    sources="[]",
                    mode=modo,
                    no_info=sin_info,
                    created_at=momento,
                )
            )
        session.commit()
    return cid
