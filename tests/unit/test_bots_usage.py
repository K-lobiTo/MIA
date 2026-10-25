"""Consumo mensual y estado de un bot de WhatsApp (feature 011): mes, incremento atómico, tope y dominios que ve."""

import uuid
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from sqlalchemy.exc import IntegrityError

from mia.bots.status import (
    REASON_ARTIFACT_DISABLED,
    REASON_BOT_DISABLED,
    REASON_CAP_REACHED,
    REASON_NO_ARTIFACT,
    bot_state,
    domain_labels,
    find_bot_by_number,
)
from mia.bots.usage import MonthUsage, add_messages, cap_reached, current_month, month_usage
from mia.config import settings
from mia.storage.models import Bot, BotMessageCount, Domain, Unit


def _bot(db, artifact_id=None, *, active=True, number="111", name="Bot de prueba"):
    bot_id = str(uuid.uuid4())
    with db() as session:
        session.add(Bot(id=bot_id, name=name, kapso_number_id=number, artifact_id=artifact_id, active=active))
        session.commit()
    return bot_id


def _sembrar(db):
    with db() as session:
        session.add_all([Unit(id="u1", name="Unidad de Postgrados de Computación"), Unit(id="u2", name="Analítica")])
        session.flush()
        session.add_all([
            Domain(id="d1", unit_id="u1", name="Admisión"),
            Domain(id="d2", unit_id="u1", name="Plan de estudios"),
            Domain(id="d3", unit_id="u2", name="Costos"),
            Domain(id="d4", unit_id=None, name="Sin programa"),
        ])
        session.commit()


# --- current_month ---------------------------------------------------------------------------------------------


def test_el_mes_es_aaaa_mm_en_la_zona_de_los_topes(monkeypatch):
    monkeypatch.setattr(settings, "cap_timezone", "America/Costa_Rica")  # UTC-6 todo el año
    assert current_month(datetime(2026, 10, 15, 12, 0, tzinfo=UTC)) == "2026-10"
    assert current_month(datetime(2026, 10, 15, 12, 0)) == "2026-10"  # noqa: DTZ001 (sin zona se toma como UTC)


def test_el_cambio_de_mes_se_corta_a_medianoche_local_no_de_utc(monkeypatch):
    monkeypatch.setattr(settings, "cap_timezone", "America/Costa_Rica")
    # 04:30 UTC del 1 de noviembre son las 22:30 del 31 de octubre en Costa Rica.
    assert current_month(datetime(2026, 11, 1, 4, 30, tzinfo=UTC)) == "2026-10"
    # 06:00 UTC es la medianoche local: ya es noviembre.
    assert current_month(datetime(2026, 11, 1, 6, 0, tzinfo=UTC)) == "2026-11"


def test_el_mes_actual_por_defecto_tiene_el_formato():
    mes = current_month()
    assert len(mes) == 7 and mes[4] == "-" and mes[:4].isdigit() and mes[5:].isdigit()


# --- add_messages y month_usage --------------------------------------------------------------------------------


def test_sin_fila_el_consumo_es_cero(db):
    bot_id = _bot(db)
    with db() as session:
        assert month_usage(session, bot_id, "2026-10") == MonthUsage(0, 0)
        assert month_usage(session, bot_id, "2026-10").total == 0


def test_add_messages_crea_la_fila_del_mes_y_suma_a_la_existente(db):
    bot_id = _bot(db)
    with db() as session:
        add_messages(session, bot_id, "2026-10", 1, 0)
        add_messages(session, bot_id, "2026-10", 1, 2)
        add_messages(session, bot_id, "2026-10", 0, 1)
        usage = month_usage(session, bot_id, "2026-10")
    assert (usage.received, usage.sent, usage.total) == (2, 3, 5)


def test_un_mes_nuevo_nace_en_cero_sin_tocar_el_anterior(db):
    bot_id = _bot(db)
    with db() as session:
        add_messages(session, bot_id, "2026-10", 5, 7)
        add_messages(session, bot_id, "2026-11", 1, 0)
        assert month_usage(session, bot_id, "2026-10").total == 12
        assert month_usage(session, bot_id, "2026-11").total == 1
        assert session.query(BotMessageCount).count() == 2


def test_el_consumo_de_un_bot_no_toca_el_de_otro(db):
    uno = _bot(db, number="1", name="Uno")
    dos = _bot(db, number="2", name="Dos")
    with db() as session:
        add_messages(session, uno, "2026-10", 3, 3)
        assert month_usage(session, dos, "2026-10").total == 0


def test_la_insercion_simultanea_repite_el_incremento_sin_perder_cuentas(db):
    """Otro proceso insertó la fila del mes entre el UPDATE que no encontró nada y el INSERT: el conflicto de clave
    se resuelve repitiendo el UPDATE. Se simula inyectando el conflicto, no con hilos (SQLite da `database is locked`)."""
    bot_id = _bot(db)
    with db() as session:
        add_messages(session, bot_id, "2026-10", 1, 0)  # la fila "del otro proceso"

    with db() as session:
        llamadas = {"n": 0}
        from mia.bots import usage as modulo

        original = modulo._increment

        def increment(sess, bid, month, received, sent):
            llamadas["n"] += 1
            if llamadas["n"] == 1:
                return 0  # el primer UPDATE "no encuentra" la fila (todavía no estaba)
            return original(sess, bid, month, received, sent)

        with patch.object(modulo, "_increment", increment):
            add_messages(session, bot_id, "2026-10", 1, 1)  # el INSERT choca con la fila existente
        assert llamadas["n"] == 2
        usage = month_usage(session, bot_id, "2026-10")
    assert (usage.received, usage.sent) == (2, 1)


def test_sumas_seguidas_no_pierden_cuentas(db):
    bot_id = _bot(db)
    with db() as session:
        for _ in range(50):
            add_messages(session, bot_id, "2026-10", 1, 1)
        assert month_usage(session, bot_id, "2026-10") == MonthUsage(50, 50)


# --- cap_reached -----------------------------------------------------------------------------------------------


@pytest.mark.parametrize(("total", "esperado"), [(0, False), (1799, False), (1800, True), (1801, True)])
def test_el_tope_se_alcanza_al_llegar_a_el(total, esperado):
    assert cap_reached(total, 1800) is esperado


# --- bot_state -------------------------------------------------------------------------------------------------


def test_un_bot_activo_con_artefacto_activo_esta_ok(db, make_artifact):
    artefacto = make_artifact(all_domains=True)
    bot_id = _bot(db, artefacto.id)
    with db() as session:
        estado = bot_state(session, session.get(Bot, bot_id), "2026-10")
    assert estado.status == "ok" and estado.reason is None and estado.available
    assert estado.cap == settings.bot_monthly_message_cap and estado.artifact.id == artefacto.id


def test_un_bot_desactivado_no_esta_disponible(db, make_artifact):
    bot_id = _bot(db, make_artifact(all_domains=True).id, active=False)
    with db() as session:
        estado = bot_state(session, session.get(Bot, bot_id), "2026-10")
    assert (estado.status, estado.reason, estado.available) == ("disabled", REASON_BOT_DISABLED, False)


def test_un_bot_sin_artefacto_no_esta_disponible(db):
    bot_id = _bot(db, None)
    with db() as session:
        estado = bot_state(session, session.get(Bot, bot_id), "2026-10")
    assert (estado.status, estado.reason, estado.artifact) == ("disabled", REASON_NO_ARTIFACT, None)


def test_un_artefacto_desactivado_deja_al_bot_no_disponible(db, make_artifact):
    bot_id = _bot(db, make_artifact(all_domains=True, active=False).id)
    with db() as session:
        estado = bot_state(session, session.get(Bot, bot_id), "2026-10")
    assert (estado.status, estado.reason) == ("disabled", REASON_ARTIFACT_DISABLED)


def test_con_el_tope_alcanzado_el_estado_es_cap_reached(db, make_artifact, monkeypatch):
    monkeypatch.setattr(settings, "bot_monthly_message_cap", 5)
    bot_id = _bot(db, make_artifact(all_domains=True).id)
    with db() as session:
        add_messages(session, bot_id, "2026-10", 3, 1)
        assert bot_state(session, session.get(Bot, bot_id), "2026-10").status == "ok"
        add_messages(session, bot_id, "2026-10", 0, 1)
        estado = bot_state(session, session.get(Bot, bot_id), "2026-10")
    assert (estado.status, estado.reason, estado.usage.total) == ("cap_reached", REASON_CAP_REACHED, 5)
    assert not estado.available


def test_cap_reached_gana_sobre_disabled(db, make_artifact, monkeypatch):
    monkeypatch.setattr(settings, "bot_monthly_message_cap", 2)
    bot_id = _bot(db, make_artifact(all_domains=True).id, active=False)
    with db() as session:
        add_messages(session, bot_id, "2026-10", 1, 1)
        assert bot_state(session, session.get(Bot, bot_id), "2026-10").status == "cap_reached"


def test_el_tope_cuenta_solo_el_mes_consultado(db, make_artifact, monkeypatch):
    monkeypatch.setattr(settings, "bot_monthly_message_cap", 2)
    bot_id = _bot(db, make_artifact(all_domains=True).id)
    with db() as session:
        add_messages(session, bot_id, "2026-10", 1, 1)
        assert bot_state(session, session.get(Bot, bot_id), "2026-10").status == "cap_reached"
        assert bot_state(session, session.get(Bot, bot_id), "2026-11").status == "ok"


# --- find_bot_by_number y domain_labels ------------------------------------------------------------------------


def test_se_busca_el_bot_por_el_numero_de_kapso(db):
    bot_id = _bot(db, number="647015955153740")
    with db() as session:
        assert find_bot_by_number(session, "647015955153740").id == bot_id
        assert find_bot_by_number(session, "999") is None


def test_los_dominios_que_ve_el_bot_por_unidad_por_dominio_y_a_todos(db, make_artifact):
    _sembrar(db)
    por_unidad = make_artifact("Por unidad", units=["u1"])
    puntual = make_artifact("Puntual", domains=["d3", "d4"])
    todos = make_artifact("Todos", all_domains=True)
    with db() as session:
        from mia.storage.models import Artifact

        assert domain_labels(session, session.get(Artifact, por_unidad.id)) == [
            "Unidad de Postgrados de Computación / Admisión",
            "Unidad de Postgrados de Computación / Plan de estudios",
        ]
        assert domain_labels(session, session.get(Artifact, puntual.id)) == ["Analítica / Costos", "Sin programa"]
        assert len(domain_labels(session, session.get(Artifact, todos.id))) == 4
        assert domain_labels(session, None) == []


def test_un_cambio_de_accesos_se_ve_en_los_dominios_de_la_lectura_siguiente(db, make_artifact):
    _sembrar(db)
    artefacto = make_artifact("Cambiante", domains=["d1"])
    with db() as session:
        from mia.storage.models import Artifact, ArtifactDomain

        assert domain_labels(session, session.get(Artifact, artefacto.id)) == [
            "Unidad de Postgrados de Computación / Admisión"
        ]
        session.add(ArtifactDomain(artifact_id=artefacto.id, domain_id="d3"))
        session.commit()
        assert len(domain_labels(session, session.get(Artifact, artefacto.id))) == 2


def test_el_nombre_y_el_numero_de_un_bot_son_unicos_en_la_base(db):
    _bot(db, number="111", name="Uno")
    with pytest.raises(IntegrityError):
        _bot(db, number="111", name="Otro")
