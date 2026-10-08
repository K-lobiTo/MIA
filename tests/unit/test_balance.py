from datetime import timedelta
from decimal import Decimal

import httpx
import pytest

from mia.access.caps import day_start_utc
from mia.config import settings
from mia.storage.models import QueryLog
from mia.usage import balance


@pytest.fixture
def llamadas(monkeypatch):
    """Respuestas de OpenRouter simuladas, por dirección; registra qué clave se usó en cada llamada."""
    monkeypatch.setattr(settings, "openrouter_api_key", "clave-normal")
    monkeypatch.setattr(settings, "openrouter_management_key", "")
    respuestas: dict[str, object] = {}
    claves: list[tuple[str, str]] = []

    def falso(url: str, key: str):
        claves.append((url, key))
        respuesta = respuestas[url]
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta

    monkeypatch.setattr(balance, "_fetch_json", falso)
    falso.respuestas, falso.claves = respuestas, claves
    return falso


def _gastar_en_la_semana(db, total):
    """Reparte `total` USD de gasto entre los últimos 7 días."""
    with db() as session:
        for dia in range(7):
            session.add(QueryLog(id=f"s{dia}", created_at=day_start_utc() - timedelta(days=dia) + timedelta(hours=1),
                                 outcome="answered", cost_usd=Decimal(str(total / 7))))
        session.commit()


KEY = "https://openrouter.ai/api/v1/key"
CREDITS = "https://openrouter.ai/api/v1/credits"


def test_con_solo_el_limite_de_la_clave(client, admin, db, llamadas):
    llamadas.respuestas[KEY] = {"data": {"limit_remaining": 11.4}}
    _gastar_en_la_semana(db, 3.5)  # 0.5 USD por día

    body = client.get("/usage/balance", headers=admin).json()

    assert body["available"] is True and body["source"] == "key_limit"
    assert body["remaining_usd"] == pytest.approx(11.4) and body["key_limit_remaining_usd"] == pytest.approx(11.4)
    assert body["account_remaining_usd"] is None
    assert body["avg_daily_spend_usd_7d"] == pytest.approx(0.5) and body["days_left"] == pytest.approx(22.8, abs=0.1)
    assert body["warning"] is False
    assert llamadas.claves == [(KEY, "clave-normal")]


def test_con_clave_de_gestion_toma_el_menor_de_los_dos(client, admin, db, llamadas, monkeypatch):
    monkeypatch.setattr(settings, "openrouter_management_key", "clave-gestion")
    llamadas.respuestas[KEY] = {"data": {"limit_remaining": 28.0}}
    llamadas.respuestas[CREDITS] = {"data": {"total_credits": 15.0, "total_usage": 3.0}}

    body = client.get("/usage/balance", headers=admin).json()

    assert body["remaining_usd"] == pytest.approx(12.0) and body["source"] == "account"
    assert body["key_limit_remaining_usd"] == pytest.approx(28.0) and body["account_remaining_usd"] == pytest.approx(12.0)
    assert (CREDITS, "clave-gestion") in llamadas.claves


def test_si_el_limite_de_la_clave_es_menor_que_el_saldo_de_la_cuenta(client, admin, llamadas, monkeypatch):
    monkeypatch.setattr(settings, "openrouter_management_key", "clave-gestion")
    llamadas.respuestas[KEY] = {"data": {"limit_remaining": 5.0}}
    llamadas.respuestas[CREDITS] = {"data": {"total_credits": 50.0, "total_usage": 1.0}}

    body = client.get("/usage/balance", headers=admin).json()

    assert body["remaining_usd"] == pytest.approx(5.0) and body["source"] == "key_limit"


def test_avisa_si_alcanza_para_menos_de_una_semana(client, admin, db, llamadas):
    llamadas.respuestas[KEY] = {"data": {"limit_remaining": 2.0}}
    _gastar_en_la_semana(db, 7.0)  # 1 USD por día

    body = client.get("/usage/balance", headers=admin).json()

    assert body["days_left"] == pytest.approx(2.0) and body["warning"] is True


def test_sin_gasto_reciente_no_se_puede_proyectar(client, admin, db, llamadas):
    llamadas.respuestas[KEY] = {"data": {"limit_remaining": 10.0}}

    body = client.get("/usage/balance", headers=admin).json()

    assert body["available"] is True and body["days_left"] is None and body["warning"] is False
    assert body["avg_daily_spend_usd_7d"] == 0


def test_sin_limite_en_la_clave_ni_clave_de_gestion_no_esta_disponible(client, admin, llamadas):
    llamadas.respuestas[KEY] = {"data": {"limit_remaining": None}}

    body = client.get("/usage/balance", headers=admin).json()

    assert body["available"] is False
    assert "límite de crédito" in body["reason"] and "clave de gestión" in body["reason"]


def test_sin_clave_de_openrouter_no_hace_ninguna_llamada(client, admin, llamadas, monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", "")

    body = client.get("/usage/balance", headers=admin).json()

    assert body["available"] is False and "OPENROUTER_API_KEY" in body["reason"]
    assert llamadas.claves == []


def test_un_error_de_red_no_rompe_el_modulo(client, admin, llamadas):
    llamadas.respuestas[KEY] = TimeoutError("sin respuesta")

    response = client.get("/usage/balance", headers=admin)

    assert response.status_code == 200
    assert response.json()["available"] is False and "No se pudo consultar" in response.json()["reason"]


def test_si_falla_solo_la_clave_de_gestion_se_usa_el_limite_de_la_clave(client, admin, llamadas, monkeypatch):
    monkeypatch.setattr(settings, "openrouter_management_key", "clave-gestion")
    llamadas.respuestas[KEY] = {"data": {"limit_remaining": 9.0}}
    llamadas.respuestas[CREDITS] = httpx.HTTPError("403 Forbidden")

    body = client.get("/usage/balance", headers=admin).json()

    assert body["available"] is True and body["remaining_usd"] == pytest.approx(9.0) and body["source"] == "key_limit"


def test_un_error_http_se_explica_sin_texto_tecnico_ni_urls(client, admin, llamadas):
    respuesta = httpx.Response(401, request=httpx.Request("GET", KEY))
    llamadas.respuestas[KEY] = httpx.HTTPStatusError("Client error '401 Unauthorized' for url", request=respuesta.request, response=respuesta)

    reason = client.get("/usage/balance", headers=admin).json()["reason"]

    assert "401" in reason and "clave" in reason
    assert "http" not in reason and "mozilla" not in reason


def test_un_fallo_de_conexion_o_de_formato_tiene_su_propio_mensaje(client, admin, llamadas):
    llamadas.respuestas[KEY] = httpx.ConnectError("boom")
    assert "conectar" in client.get("/usage/balance", headers=admin).json()["reason"]

    for raro in (["no es un objeto"], {"sin": "data"}, {"data": "texto"}, None):
        llamadas.respuestas[KEY] = raro
        respuesta = client.get("/usage/balance", headers=admin)
        assert respuesta.status_code == 200 and "formato" in respuesta.json()["reason"], raro
