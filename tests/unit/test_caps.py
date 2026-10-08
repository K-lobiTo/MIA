from datetime import UTC, datetime
from decimal import Decimal

import pytest

from mia.access import caps
from mia.config import settings
from mia.storage.models import Artifact, QueryLog


@pytest.fixture(autouse=True)
def zona(monkeypatch):
    monkeypatch.setattr(settings, "cap_timezone", "America/Costa_Rica")  # UTC-6, sin horario de verano


def _utc(*args) -> datetime:
    return datetime(*args, tzinfo=UTC)


def _naive(*args) -> datetime:
    """UTC sin zona: así se guardan las fechas en la base y así las devuelve el módulo de topes."""
    return datetime(*args, tzinfo=UTC).replace(tzinfo=None)


def test_el_dia_empieza_a_medianoche_de_costa_rica_no_de_utc():
    # 23:30 del 8 de octubre en Costa Rica ya es el 9 en UTC (05:30).
    ahora = _utc(2026, 10, 9, 5, 30)

    assert caps.day_start_utc(ahora) == _naive(2026, 10, 8, 6, 0)  # 00:00 CR del 8, en UTC naive
    assert caps.next_reset_utc(ahora) == _naive(2026, 10, 9, 6, 0)


def test_pasada_la_medianoche_local_empieza_otro_dia():
    ahora = _utc(2026, 10, 9, 6, 30)  # 00:30 del 9 en Costa Rica

    assert caps.day_start_utc(ahora) == _naive(2026, 10, 9, 6, 0)
    assert caps.next_reset_utc(ahora) == _naive(2026, 10, 10, 6, 0)


def test_sin_hora_dada_usa_la_actual_y_acepta_fechas_sin_zona():
    assert caps.day_start_utc() <= datetime.now(UTC).replace(tzinfo=None)
    assert caps.day_start_utc(_naive(2026, 10, 9, 5, 30)) == _naive(2026, 10, 8, 6, 0)  # naive se toma como UTC


def _registro(session, id_, artifact_id, *, cuando, costo, modo="literal", resultado="answered"):
    session.add(
        QueryLog(id=id_, artifact_id=artifact_id, created_at=cuando.replace(tzinfo=None), mode=modo,
                 outcome=resultado, cost_usd=Decimal(str(costo)))
    )


def _artefactos(db):
    with db() as session:
        for id_ in ("a", "b"):
            session.add(Artifact(id=id_, name=id_, key_hash=f"h{id_}", key_prefix="mia_xxxx"))
        session.commit()


def test_la_suma_solo_cuenta_el_dia_de_costa_rica(db):
    _artefactos(db)
    ahora = _utc(2026, 10, 9, 5, 30)  # 23:30 del 8 en Costa Rica
    with db() as session:
        _registro(session, "ayer", "a", cuando=_utc(2026, 10, 8, 5, 59), costo=9)  # 23:59 del 7 en CR: no cuenta
        _registro(session, "hoy1", "a", cuando=_utc(2026, 10, 8, 6, 0), costo=0.25)  # 00:00 del 8 en CR: sí
        _registro(session, "hoy2", "a", cuando=_utc(2026, 10, 9, 5, 0), costo=0.50)  # 23:00 del 8 en CR: sí
        session.commit()

        assert caps.spent_today(session, now=ahora) == Decimal("0.75")


def test_la_suma_por_artefacto_y_por_modo(db):
    _artefactos(db)
    ahora = _utc(2026, 10, 8, 18, 0)
    cuando = _utc(2026, 10, 8, 12, 0)
    with db() as session:
        _registro(session, "q1", "a", cuando=cuando, costo=0.10, modo="literal")
        _registro(session, "q2", "a", cuando=cuando, costo=0.30, modo="razonamiento")
        _registro(session, "q3", "b", cuando=cuando, costo=1.00, modo="razonamiento")
        session.commit()

        assert caps.spent_today(session, now=ahora) == Decimal("1.40")
        assert caps.spent_today(session, artifact_id="a", now=ahora) == Decimal("0.40")
        assert caps.spent_today(session, artifact_id="a", mode="razonamiento", now=ahora) == Decimal("0.30")
        assert caps.spent_today(session, artifact_id="b", mode="literal", now=ahora) == Decimal(0)


def test_las_rechazadas_con_costo_cero_no_suman(db):
    _artefactos(db)
    with db() as session:
        _registro(session, "r1", "a", cuando=_utc(2026, 10, 8, 12, 0), costo=0, resultado="rejected_cap")
        session.commit()

        assert caps.spent_today(session, now=_utc(2026, 10, 8, 18, 0)) == Decimal(0)


def _artefacto(session, *, tope, razonamiento=None):
    artefacto = session.get(Artifact, "a")
    artefacto.daily_cap_usd = Decimal(str(tope))
    artefacto.reasoning_daily_cap_usd = None if razonamiento is None else Decimal(str(razonamiento))
    session.commit()
    return artefacto


def test_check_caps_sin_tope_alcanzado_no_devuelve_nada(db):
    _artefactos(db)
    ahora = _utc(2026, 10, 8, 18, 0)
    with db() as session:
        _registro(session, "q1", "a", cuando=_utc(2026, 10, 8, 12, 0), costo=0.10)
        artefacto = _artefacto(session, tope=0.50)
        session.commit()

        assert caps.check_caps(session, artefacto, "literal", now=ahora) is None


def test_check_caps_orden_global_artefacto_razonamiento(db, monkeypatch):
    _artefactos(db)
    ahora = _utc(2026, 10, 8, 18, 0)
    cuando = _utc(2026, 10, 8, 12, 0)
    with db() as session:
        _registro(session, "q1", "a", cuando=cuando, costo=0.40, modo="razonamiento")
        session.commit()
        artefacto = _artefacto(session, tope=0.40, razonamiento=0.40)

        # Con los tres topes alcanzados, el primero que se informa es el de toda la API.
        monkeypatch.setattr(settings, "daily_cap_usd", 0.40)
        assert caps.check_caps(session, artefacto, "razonamiento", now=ahora).scope == "api"
        monkeypatch.setattr(settings, "daily_cap_usd", 3.0)
        assert caps.check_caps(session, artefacto, "razonamiento", now=ahora).scope == "artifact"
        # Solo el tope de razonamiento alcanzado: el modo literal sigue disponible.
        artefacto = _artefacto(session, tope=1.00, razonamiento=0.40)
        assert caps.check_caps(session, artefacto, "razonamiento", now=ahora).scope == "reasoning"
        assert caps.check_caps(session, artefacto, "literal", now=ahora) is None


def test_el_tope_se_alcanza_al_igualarlo(db):
    _artefactos(db)
    with db() as session:
        _registro(session, "q1", "a", cuando=_utc(2026, 10, 8, 12, 0), costo=0.50)
        artefacto = _artefacto(session, tope=0.50)

        estado = caps.check_caps(session, artefacto, "literal", now=_utc(2026, 10, 8, 18, 0))

        assert estado.scope == "artifact" and estado.cap == Decimal("0.5") and estado.spent == Decimal("0.5")
        assert estado.resets_at == _naive(2026, 10, 9, 6, 0)


def test_el_gasto_de_ayer_no_bloquea_hoy(db):
    _artefactos(db)
    with db() as session:
        _registro(session, "q1", "a", cuando=_utc(2026, 10, 7, 12, 0), costo=5)
        artefacto = _artefacto(session, tope=0.50)

        assert caps.check_caps(session, artefacto, "literal", now=_utc(2026, 10, 8, 18, 0)) is None


def test_estado_del_artefacto_para_config_y_listado(db, monkeypatch):
    _artefactos(db)
    monkeypatch.setattr(settings, "daily_cap_usd", 3.0)
    ahora = _utc(2026, 10, 8, 18, 0)
    with db() as session:
        _registro(session, "q1", "a", cuando=_utc(2026, 10, 8, 12, 0), costo=0.30, modo="razonamiento")
        _registro(session, "q2", "a", cuando=_utc(2026, 10, 8, 12, 5), costo=0.10, modo="literal")
        artefacto = _artefacto(session, tope=0.40, razonamiento=0.30)

        estado = caps.artifact_status(session, artefacto, now=ahora)

        assert estado.spent == Decimal("0.40") and estado.reasoning_spent == Decimal("0.30")
        assert estado.cap_reached is True and estado.reasoning_cap_reached is True
        assert estado.global_cap_reached is False
        assert estado.resets_at == _naive(2026, 10, 9, 6, 0)


def test_segundos_hasta_el_reinicio():
    assert caps.seconds_until(_naive(2026, 10, 9, 6, 0), now=_utc(2026, 10, 9, 5, 0)) == 3600
    assert caps.seconds_until(_naive(2026, 10, 9, 6, 0), now=_utc(2026, 10, 9, 7, 0)) == 0
