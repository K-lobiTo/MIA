"""Retención, limpieza y borrado de conversaciones (feature 015, US5)."""

import logging
import uuid
from datetime import timedelta

import pytest

from mia.chat import retention
from mia.config import settings
from mia.storage.models import ConsultaSession, ConsultaUser, Conversation, ConversationTurn, _now
from tests.unit.chat_de_prueba import crear_usuario, iniciar_sesion, sembrar_conversacion


@pytest.fixture(autouse=True)
def reloj_de_limpieza():
    retention.reset_purge_clock()
    yield
    retention.reset_purge_clock()


def _contar(db):
    with db() as session:
        return session.query(Conversation).count(), session.query(ConversationTurn).count()


# --- Borrado por la persona -----------------------------------------------------------------------------------------


def test_borrar_una_conversacion_no_deja_ninguna_fila_suya(client, db):
    ana = iniciar_sesion(db)
    borrar = sembrar_conversacion(db, ana["uid"], vueltas=3)
    conservar = sembrar_conversacion(db, ana["uid"], vueltas=2)

    respuesta = client.delete(f"/conversations/{borrar}", headers=ana["headers"])

    assert respuesta.status_code == 204
    with db() as session:
        assert session.get(Conversation, borrar) is None
        assert session.query(ConversationTurn).filter_by(conversation_id=borrar).count() == 0
        assert session.query(ConversationTurn).filter_by(conversation_id=conservar).count() == 2


def test_borrar_todas_no_toca_las_de_otro_usuario_y_es_idempotente(client, db):
    ana = iniciar_sesion(db, "ana")
    beto = iniciar_sesion(db, "beto")
    sembrar_conversacion(db, ana["uid"], 2)
    sembrar_conversacion(db, ana["uid"], 3)
    de_beto = sembrar_conversacion(db, beto["uid"], 4)

    assert client.delete("/conversations", headers=ana["headers"]).status_code == 204
    assert (
        client.delete("/conversations", headers=ana["headers"]).status_code == 204
    )  # sin nada que borrar

    assert _contar(db) == (1, 4)
    with db() as session:
        assert session.get(Conversation, de_beto) is not None


def test_borrar_una_ajena_o_inexistente_da_el_mismo_404_y_no_borra_nada(client, db):
    ana = iniciar_sesion(db, "ana")
    beto = iniciar_sesion(db, "beto")
    de_ana = sembrar_conversacion(db, ana["uid"], 2)

    ajena = client.delete(f"/conversations/{de_ana}", headers=beto["headers"])
    falsa = client.delete(f"/conversations/{uuid.uuid4()}", headers=beto["headers"])

    assert ajena.status_code == falsa.status_code == 404 and ajena.json() == falsa.json()
    assert _contar(db) == (1, 2)


def test_borrar_exige_sesion(client, db):
    assert client.delete("/conversations").json()["code"] == "session_invalid"
    assert client.delete(f"/conversations/{uuid.uuid4()}").status_code == 401


# --- Limpieza por retención -----------------------------------------------------------------------------------------


def test_purge_borra_las_sin_actividad_por_mas_de_la_retencion_con_sus_vueltas_y_conserva_las_recientes(
    db, monkeypatch
):
    monkeypatch.setattr(settings, "chat_retention_days", 30)
    uid = crear_usuario(db)
    vieja = sembrar_conversacion(db, uid, 3, hace_dias=31)
    limite = sembrar_conversacion(db, uid, 1, hace_dias=29)
    reciente = sembrar_conversacion(db, uid, 2, hace_dias=1)

    with db() as session:
        resultado = retention.purge_expired(session)

    assert resultado["conversations"] == 1
    with db() as session:
        assert session.get(Conversation, vieja) is None
        assert session.query(ConversationTurn).filter_by(conversation_id=vieja).count() == 0
        assert (
            session.get(Conversation, limite) is not None
            and session.get(Conversation, reciente) is not None
        )
        assert session.query(ConversationTurn).count() == 3


def test_purge_borra_las_de_un_usuario_desactivado_cuando_vencen_y_no_toca_usuarios_ni_contrasenas(
    db, monkeypatch
):
    monkeypatch.setattr(settings, "chat_retention_days", 30)
    uid = crear_usuario(db, "baja", activo=False)
    sembrar_conversacion(db, uid, 2, hace_dias=60)

    with db() as session:
        retention.purge_expired(session)

    with db() as session:
        usuario = session.get(ConsultaUser, uid)
        assert usuario is not None and usuario.password_hash.startswith("scrypt$")
        assert session.query(Conversation).count() == 0


def test_purge_borra_las_sesiones_vencidas(db, monkeypatch):
    monkeypatch.setattr(settings, "chat_retention_days", 30)
    ana = iniciar_sesion(db)
    with db() as session:
        session.query(ConsultaSession).update({"expires_at": _now() - timedelta(minutes=1)})
        session.commit()

    with db() as session:
        resultado = retention.purge_expired(session)
        assert resultado["sessions"] == 1 and session.query(ConsultaSession).count() == 0
    assert ana["uid"]


def test_con_retencion_cero_se_borran_todas_las_conversaciones_y_no_se_guarda_nada_mas(
    db, monkeypatch
):
    monkeypatch.setattr(settings, "chat_retention_days", 0)
    uid = crear_usuario(db)
    sembrar_conversacion(db, uid, 3)
    sembrar_conversacion(db, uid, 1, hace_dias=0)

    with db() as session:
        retention.purge_expired(session)

    assert _contar(db) == (0, 0)
    with db() as session:
        assert session.get(ConsultaUser, uid) is not None  # los usuarios quedan


def test_maybe_purge_corre_una_vez_por_hora_por_proceso(db, monkeypatch):
    monkeypatch.setattr(settings, "chat_retention_days", 30)
    uid = crear_usuario(db)
    ahora = [1_000.0]
    with db() as session:
        sembrar_conversacion(db, uid, 1, hace_dias=40)
        assert retention.maybe_purge(session, clock=lambda: ahora[0]) is True
        sembrar_conversacion(db, uid, 1, hace_dias=40)
        assert (
            retention.maybe_purge(session, clock=lambda: ahora[0]) is False
        )  # aún no pasó una hora
        assert session.query(Conversation).count() == 1
        ahora[0] += 3601
        assert retention.maybe_purge(session, clock=lambda: ahora[0]) is True
        assert session.query(Conversation).count() == 0


def test_las_rutas_de_sesion_y_de_conversaciones_disparan_la_limpieza_perezosa(
    client, db, monkeypatch
):
    monkeypatch.setattr(settings, "chat_retention_days", 30)
    ana = iniciar_sesion(db)
    vieja = sembrar_conversacion(db, ana["uid"], 1, hace_dias=45)

    lista = client.get("/conversations", headers=ana["headers"]).json()

    assert lista["conversations"] == []
    with db() as session:
        assert session.get(Conversation, vieja) is None
    # También al iniciar sesión.
    retention.reset_purge_clock()
    otra = sembrar_conversacion(db, ana["uid"], 1, hace_dias=45)
    assert (
        client.post(
            "/auth/login", json={"username": "ana", "password": "una-clave-larga-123"}
        ).status_code
        == 200
    )
    with db() as session:
        assert session.get(Conversation, otra) is None


def test_la_api_corre_la_limpieza_al_arrancar_sin_impedirlo_si_falla(db, monkeypatch, caplog):
    monkeypatch.setattr(settings, "chat_retention_days", 30)
    uid = crear_usuario(db)
    vieja = sembrar_conversacion(db, uid, 1, hace_dias=45)
    monkeypatch.setattr(retention, "SessionLocal", db)

    retention.purge_on_startup()

    with db() as session:
        assert session.get(Conversation, vieja) is None

    def roto():
        raise RuntimeError("base caída")

    monkeypatch.setattr(retention, "SessionLocal", roto)
    with caplog.at_level(logging.WARNING):
        retention.purge_on_startup()  # no lanza
    assert "limpieza" in caplog.text.lower()


def test_el_registro_de_la_limpieza_escribe_solo_cantidades(db, monkeypatch, caplog):
    monkeypatch.setattr(settings, "chat_retention_days", 30)
    uid = crear_usuario(db)
    sembrar_conversacion(db, uid, 1, titulo="titulo-secreto-123", hace_dias=45)

    with caplog.at_level(logging.DEBUG), db() as session:
        retention.purge_expired(session)

    assert "titulo-secreto-123" not in caplog.text
    assert "conversaciones=1" in caplog.text
