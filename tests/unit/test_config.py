import uuid
from decimal import Decimal

import pytest

from mia.config import settings
from mia.storage.models import Domain, QueryLog, Unit


@pytest.fixture
def base(db):
    with db() as session:
        session.add(Unit(id="u1", name="Computación"))
        session.flush()
        session.add(Domain(id="d1", unit_id="u1", name="Currículum"))
        session.commit()


def _modos(response):
    return {m["id"]: m for m in response.json()["modes"]}


def test_config_sin_clave_lista_ambos_modos(client, base, modes_config, monkeypatch):
    monkeypatch.setattr(settings, "ingestion_enabled", True)
    monkeypatch.setattr(settings, "max_upload_mb", 25)

    response = client.get("/config")

    assert response.status_code == 200
    body = response.json()
    assert body["ingestion_enabled"] is True and body["max_upload_mb"] == 25
    assert "artifact" not in body
    modos = _modos(response)
    assert set(modos) == {"literal", "razonamiento"}
    assert modos["literal"]["name"] == "Literal" and modos["literal"]["available"] is True
    assert modos["literal"]["reason"] is None
    assert modos["razonamiento"]["description"]


def test_un_modo_sin_proveedor_configurado_figura_no_disponible(client, base, modes_config, monkeypatch):
    monkeypatch.setattr(settings, "llm_provider_razonamiento", "")

    modos = _modos(client.get("/config"))

    assert modos["razonamiento"]["available"] is False
    assert "configurado" in modos["razonamiento"]["reason"]
    assert modos["literal"]["available"] is True


def test_openrouter_sin_modelo_no_esta_disponible(client, base, modes_config, monkeypatch):
    monkeypatch.setattr(settings, "llm_model_literal", "")
    monkeypatch.setattr(settings, "openrouter_model", "")

    modos = _modos(client.get("/config"))

    assert modos["literal"]["available"] is False


def test_el_modo_literal_usa_la_configuracion_anterior_si_no_define_la_suya(client, base, modes_config, monkeypatch):
    monkeypatch.setattr(settings, "llm_provider_literal", "")
    monkeypatch.setattr(settings, "llm_provider", "openrouter")
    monkeypatch.setattr(settings, "llm_model_literal", "")
    monkeypatch.setattr(settings, "openrouter_model", "z-ai/glm-5.3-flash")

    modos = _modos(client.get("/config"))

    assert modos["literal"]["available"] is True


def test_con_clave_de_artefacto_solo_los_modos_permitidos(client, base, modes_config, make_artifact):
    artefacto = make_artifact("Consulta Computación", modes="literal", units=["u1"])

    response = client.get("/config", headers=artefacto.headers)

    assert response.status_code == 200
    assert set(_modos(response)) == {"literal"}
    assert response.json()["artifact"] == {
        "name": "Consulta Computación",
        "active": True,
        "context_turns": 0,
        "require_login": False,  # feature 015
    }


def test_un_artefacto_con_ambos_modos_los_ve_ambos(client, base, modes_config, make_artifact):
    artefacto = make_artifact(modes="literal,razonamiento", all_domains=True)

    assert set(_modos(client.get("/config", headers=artefacto.headers))) == {"literal", "razonamiento"}


def test_clave_de_artefacto_invalida_responde_401(client, base, modes_config):
    assert client.get("/config", headers={"X-Artifact-Key": "mia_falsa"}).status_code == 401


def test_dominios_con_clave_de_artefacto_solo_los_permitidos(client, db, base, make_artifact, admin):
    with db() as session:
        session.add(Domain(id="d2", unit_id="u1", name="Docentes"))
        session.commit()
    artefacto = make_artifact(domains=["d2"])

    todos = client.get("/domains", headers=admin).json()
    permitidos = client.get("/domains", headers=artefacto.headers).json()

    assert {d["name"] for d in todos} == {"Currículum", "Docentes"}
    assert [d["name"] for d in permitidos] == ["Docentes"]
    assert permitidos[0]["unit_name"] == "Computación"


# ----- Topes en la configuración que ve cada artefacto (US4) -----


def _gastar(db, artifact_id, costo, modo="literal"):
    with db() as session:
        session.add(QueryLog(id=str(uuid.uuid4()), artifact_id=artifact_id, mode=modo, outcome="answered",
                             model="m", cost_usd=Decimal(str(costo))))
        session.commit()


def test_config_con_clave_informa_los_topes_y_el_reinicio(client, base, modes_config, make_artifact):
    artefacto = make_artifact(modes="literal,razonamiento", all_domains=True, cap=1.0, reasoning_cap=0.5)

    body = client.get("/config", headers=artefacto.headers).json()

    assert body["caps"]["cap_reached"] is False and body["caps"]["reasoning_cap_reached"] is False
    assert body["caps"]["global_cap_reached"] is False
    assert body["caps"]["resets_at"].endswith("Z")
    assert all(m["available"] for m in body["modes"])


def test_el_modo_con_el_tope_alcanzado_figura_no_disponible_y_el_literal_sigue(client, db, base, modes_config, make_artifact):
    artefacto = make_artifact(modes="literal,razonamiento", all_domains=True, cap=1.0, reasoning_cap=0.5)
    _gastar(db, artefacto.id, 0.5, modo="razonamiento")

    body = client.get("/config", headers=artefacto.headers).json()

    modos = {m["id"]: m for m in body["modes"]}
    assert body["caps"]["reasoning_cap_reached"] is True and body["caps"]["cap_reached"] is False
    assert modos["razonamiento"]["available"] is False and "tope" in modos["razonamiento"]["reason"]
    assert modos["literal"]["available"] is True


def test_con_el_tope_total_alcanzado_ningun_modo_esta_disponible(client, db, base, modes_config, make_artifact):
    artefacto = make_artifact(modes="literal,razonamiento", all_domains=True, cap=1.0)
    _gastar(db, artefacto.id, 1.0)

    body = client.get("/config", headers=artefacto.headers).json()

    assert body["caps"]["cap_reached"] is True
    assert not any(m["available"] for m in body["modes"])


def test_con_el_tope_global_alcanzado_se_informa(client, db, base, modes_config, make_artifact, monkeypatch):
    monkeypatch.setattr(settings, "daily_cap_usd", 0.5)
    artefacto = make_artifact(all_domains=True, cap=5.0)
    _gastar(db, artefacto.id, 0.5)

    body = client.get("/config", headers=artefacto.headers).json()

    assert body["caps"]["global_cap_reached"] is True and not any(m["available"] for m in body["modes"])


# --- Búsqueda híbrida (feature 010): rangos de las variables ----------------------------------------------------


def test_los_valores_por_defecto_de_la_busqueda_hibrida_son_los_calibrados():
    from mia.config import Settings

    base = Settings(_env_file=None)
    assert base.query_hybrid_search == "off"
    assert (base.hybrid_max_docs, base.hybrid_term_chunks, base.hybrid_lexical_limit, base.hybrid_lexical_slots) == (
        10, 200, 20, 3
    )
    assert (base.hybrid_max_groups, base.hybrid_min_token_len, base.hybrid_rrf_k, base.hybrid_budget_ms) == (8, 3, 60, 800)
    assert base.hybrid_min_match_ratio == 0.5 and base.hybrid_equivalences_ttl_seconds == 60


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("hybrid_min_token_len", 2),
        ("hybrid_max_docs", 0),
        ("hybrid_term_chunks", 5),
        ("hybrid_lexical_slots", 17),
        ("hybrid_min_match_ratio", 0.0),
        ("hybrid_min_match_ratio", 1.5),
        ("hybrid_budget_ms", -1),
    ],
)
def test_un_valor_numerico_de_la_busqueda_hibrida_fuera_de_rango_no_deja_arrancar(campo, valor):
    from pydantic import ValidationError

    from mia.config import Settings

    with pytest.raises(ValidationError, match=campo):
        Settings(_env_file=None, **{campo: valor})


def test_un_valor_invalido_del_interruptor_de_la_busqueda_hibrida_se_trata_como_apagado_sin_fallar():
    from mia.config import Settings
    from mia.rag.lexical import hybrid_enabled

    # El campo es texto libre justamente para que un valor inválido no impida el arranque.
    assert Settings(_env_file=None, query_hybrid_search="quizas").query_hybrid_search == "quizas"
    assert hybrid_enabled("quizas") is False


# --- Eliminación de documentos (feature 012) ---------------------------------------------------------------------


def test_la_espera_de_la_eliminacion_vale_60_segundos_por_defecto_y_se_lee_del_entorno(monkeypatch):
    from mia.config import Settings

    assert Settings(_env_file=None).delete_wait_seconds == 60
    monkeypatch.setenv("DELETE_WAIT_SECONDS", "5")
    assert Settings(_env_file=None).delete_wait_seconds == 5


@pytest.mark.parametrize("valor", [0, 601])
def test_una_espera_de_eliminacion_fuera_de_rango_no_deja_arrancar(valor):
    from pydantic import ValidationError

    from mia.config import Settings

    with pytest.raises(ValidationError, match="delete_wait_seconds"):
        Settings(_env_file=None, delete_wait_seconds=valor)


# --- Aclaración de programa del bot (feature 013) ------------------------------------------------------------------


def test_los_valores_por_defecto_de_la_aclaracion_de_programa():
    from mia.config import Settings

    base = Settings(_env_file=None)
    assert base.bot_clarify == "off"
    assert base.bot_clarify_min_similarity == 0.70 and base.bot_clarify_max_programs == 5
    assert base.bot_clarify_candidates == 30


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("bot_clarify_min_similarity", -0.1),
        ("bot_clarify_min_similarity", 1.1),
        ("bot_clarify_max_programs", 1),
        ("bot_clarify_max_programs", 11),
        ("bot_clarify_candidates", 4),
        ("bot_clarify_candidates", 101),
    ],
)
def test_un_valor_de_la_aclaracion_fuera_de_rango_no_deja_arrancar(campo, valor):
    from pydantic import ValidationError

    from mia.config import Settings

    with pytest.raises(ValidationError, match=campo):
        Settings(_env_file=None, **{campo: valor})


@pytest.mark.parametrize(("valor", "esperado"), [("on", True), ("ON", True), ("off", False), ("", False), ("tal vez", False)])
def test_el_interruptor_de_la_aclaracion_trata_un_valor_invalido_como_apagado(valor, esperado):
    from mia.rag.completeness import switch_enabled

    assert switch_enabled(valor, "BOT_CLARIFY") is esperado


# --- Memoria de conversación (feature 014) --------------------------------------------------------------------------


def test_los_valores_por_defecto_de_la_memoria_de_conversacion():
    from mia.config import Settings

    base = Settings(_env_file=None)
    assert base.history_reformulation == "rules"
    assert (
        base.history_max_question_chars,
        base.history_max_answer_chars,
        base.history_max_chars,
    ) == (500, 1500, 6000)
    assert base.history_rewrite_max_tokens == 100


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("history_max_question_chars", 49),
        ("history_max_question_chars", 2001),
        ("history_max_answer_chars", 199),
        ("history_max_answer_chars", 20001),
        ("history_max_chars", 499),
        ("history_max_chars", 100001),
        ("history_rewrite_max_tokens", 19),
        ("history_rewrite_max_tokens", 501),
    ],
)
def test_un_valor_de_la_memoria_fuera_de_rango_no_deja_arrancar(campo, valor):
    from pydantic import ValidationError

    from mia.config import Settings

    with pytest.raises(ValidationError, match=campo):
        Settings(_env_file=None, **{campo: valor})


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [("rules", "rules"), ("MODEL", "model"), (" off ", "off"), ("", "rules"), ("tal vez", "rules")],
)
def test_la_estrategia_de_reformulacion_invalida_se_trata_como_rules(valor, esperado):
    from mia.rag.followup import strategy

    assert strategy(valor) == esperado


# --- Bot de WhatsApp (feature 011): variables de la API -------------------------------------------------------


def test_los_valores_por_defecto_del_bot_de_whatsapp():
    from mia.config import Settings

    base = Settings(_env_file=None)
    assert base.bot_service_key == ""
    assert base.bot_monthly_message_cap == 1800
    assert base.max_image_mb == 2


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("bot_monthly_message_cap", 0),
        ("bot_monthly_message_cap", 100001),
        ("max_image_mb", 0),
        ("max_image_mb", 11),
    ],
)
def test_un_valor_del_bot_de_whatsapp_fuera_de_rango_no_deja_arrancar(campo, valor):
    from pydantic import ValidationError

    from mia.config import Settings

    with pytest.raises(ValidationError, match=campo):
        Settings(_env_file=None, **{campo: valor})


# --- Usuarios de la Consulta e historial de chats (feature 015) ------------------------------------------------------


def test_los_valores_por_defecto_del_historial_de_chats():
    from mia.config import Settings

    base = Settings(_env_file=None)
    assert (base.chat_retention_days, base.chat_max_turns, base.chat_max_conversations) == (90, 200, 100)
    assert base.chat_max_answer_chars == 20000
    assert (base.session_hours, base.session_max_days) == (8, 7)
    assert (base.login_max_attempts, base.login_max_attempts_per_origin, base.login_lock_minutes) == (5, 20, 15)
    assert base.password_min_chars == 10
    assert base.trust_forwarded_for == "off"


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("chat_retention_days", -1),
        ("chat_retention_days", 3651),
        ("chat_max_turns", 1),
        ("chat_max_turns", 2001),
        ("chat_max_conversations", 0),
        ("chat_max_conversations", 5001),
        ("chat_max_answer_chars", 999),
        ("chat_max_answer_chars", 100001),
        ("session_hours", 0),
        ("session_hours", 721),
        ("session_max_days", 0),
        ("session_max_days", 91),
        ("login_max_attempts", 0),
        ("login_max_attempts", 101),
        ("login_max_attempts_per_origin", 0),
        ("login_max_attempts_per_origin", 1001),
        ("login_lock_minutes", 0),
        ("login_lock_minutes", 1441),
        ("password_min_chars", 7),
        ("password_min_chars", 129),
    ],
)
def test_un_valor_del_historial_de_chats_fuera_de_rango_no_deja_arrancar(campo, valor):
    from pydantic import ValidationError

    from mia.config import Settings

    with pytest.raises(ValidationError, match=campo):
        Settings(_env_file=None, **{campo: valor})


def test_la_retencion_en_cero_es_valida_porque_apaga_el_guardado():
    from mia.config import Settings

    assert Settings(_env_file=None, chat_retention_days=0).chat_retention_days == 0
