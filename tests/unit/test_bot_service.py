"""Rutas de la API para el servicio del bot de WhatsApp (feature 011): POST /bot/messages y POST /bot/query."""

import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from mia.api.routes import query as query_routes
from mia.bots.usage import current_month, month_usage
from mia.config import settings
from mia.rag.llm import LLMAnswer
from mia.storage.models import Artifact, ArtifactDomain, Bot, Document, Domain, QueryLog, Unit
from mia.storage.vector_store import SearchResult

CLAVE = "clave-del-servicio-de-prueba"
NUMERO = "647015955153740"


@pytest.fixture
def servicio(monkeypatch):
    """Credencial de servicio configurada en la API; devuelve los encabezados que envía el servicio del bot."""
    monkeypatch.setattr(settings, "bot_service_key", CLAVE)
    return {"X-Bot-Service-Key": CLAVE}


@pytest.fixture
def mundo(db, modes_config, make_artifact):
    with db() as session:
        session.add_all([Unit(id="u1", name="Computación"), Unit(id="u2", name="Analítica"), Unit(id="u3", name="Vacía")])
        session.flush()
        session.add_all([
            Domain(id="dom-1", unit_id="u1", name="Admisión"),
            Domain(id="dom-2", unit_id="u1", name="Plan de estudios"),
            Domain(id="dom-3", unit_id="u2", name="Costos"),
        ])
        session.flush()
        session.add(Document(id="doc-1", domain_id="dom-1", filename="requisitos.pdf", source_type="pdf", file_hash="h", status="done"))
        session.commit()
    artefacto = make_artifact("Bot de Computación", units=["u1"], modes="literal,razonamiento", cap=1.0)
    return {"artefacto": artefacto}


def _bot(db, artifact_id, *, number=NUMERO, active=True, name="Bot de pruebas"):
    bot_id = str(uuid.uuid4())
    with db() as session:
        session.add(Bot(id=bot_id, name=name, kapso_number_id=number, artifact_id=artifact_id, active=active))
        session.commit()
    return bot_id


class Pipeline:
    """Almacén de vectores, embeddings y LLM simulados, como en test_query_sources.py."""

    def __init__(self, text="La matrícula es del 3 al 7 de agosto."):
        self.store = MagicMock()
        self.store.count_chunks.return_value = 100
        self.store.search.return_value = [
            SearchResult(chunk_id="c1", document_id="doc-1", domain="dom-1", text="fragmento relevante", score=0.9)
        ]
        self.embeddings = MagicMock()
        self.embeddings.embed.return_value = [[0.1, 0.2]]
        self.llm = MagicMock()
        self.llm.answer.return_value = LLMAnswer(text=text, model="modelo", prompt_tokens=100, completion_tokens=20, cost_usd=0.0004)
        self.get_llm = MagicMock(return_value=self.llm)

    def __enter__(self):
        self._patches = [
            patch.object(query_routes, "get_vector_store", return_value=self.store),
            patch.object(query_routes, "get_embedding_provider", return_value=self.embeddings),
            patch.object(query_routes, "get_llm_provider", self.get_llm),
        ]
        for p in self._patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in self._patches:
            p.stop()

    @property
    def searched_domains(self):
        return self.store.search.call_args.kwargs["domains"]


def _pregunta(client, headers, question="¿Cuándo es la matrícula?", number=NUMERO):
    return client.post("/bot/query", json={"number_id": number, "question": question}, headers=headers)


def _mensajes(client, headers, received=0, sent=0, number=NUMERO):
    return client.post("/bot/messages", json={"number_id": number, "received": received, "sent": sent}, headers=headers)


# --- Credencial ------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("ruta", ["/bot/messages", "/bot/query"])
def test_las_dos_rutas_exigen_la_credencial_de_servicio(client, db, mundo, servicio, monkeypatch, ruta):
    _bot(db, mundo["artefacto"].id)
    cuerpo = {"number_id": NUMERO, "question": "hola"} if ruta == "/bot/query" else {"number_id": NUMERO}

    assert client.post(ruta, json=cuerpo).status_code == 401
    assert client.post(ruta, json=cuerpo, headers={"X-Bot-Service-Key": "otra"}).status_code == 401
    # La clave del artefacto y la de administración no sirven.
    monkeypatch.setattr(settings, "admin_key", "admin-de-prueba")
    otras = {**mundo["artefacto"].headers, "X-Admin-Key": "admin-de-prueba"}
    assert client.post(ruta, json=cuerpo, headers=otras).status_code == 401
    # Con la variable vacía las rutas están apagadas, ni con un encabezado vacío.
    monkeypatch.setattr(settings, "bot_service_key", "")
    assert client.post(ruta, json=cuerpo, headers={"X-Bot-Service-Key": ""}).status_code == 401
    assert client.post(ruta, json=cuerpo, headers=servicio).status_code == 401


# --- POST /bot/messages ----------------------------------------------------------------------------------------


def test_un_bot_en_orden_responde_ok_y_suma_lo_recibido(client, db, mundo, servicio):
    bot_id = _bot(db, mundo["artefacto"].id)

    cuerpo = _mensajes(client, servicio, received=1).json()

    assert cuerpo == {
        "status": "ok",
        "month": current_month(),
        "month_messages": 1,
        "month_cap": settings.bot_monthly_message_cap,
    }
    with db() as session:
        assert month_usage(session, bot_id).received == 1


def test_lo_recibido_y_lo_enviado_se_acumulan_y_persisten(client, db, mundo, servicio):
    bot_id = _bot(db, mundo["artefacto"].id)

    _mensajes(client, servicio, received=1)
    _mensajes(client, servicio, sent=2)
    cuerpo = _mensajes(client, servicio, received=1, sent=1).json()

    assert cuerpo["month_messages"] == 5
    with db() as session:
        uso = month_usage(session, bot_id)
    assert (uso.received, uso.sent) == (2, 3)


def test_con_ambos_en_cero_solo_consulta_el_estado(client, db, mundo, servicio):
    bot_id = _bot(db, mundo["artefacto"].id)
    _mensajes(client, servicio, received=3)

    cuerpo = _mensajes(client, servicio).json()

    assert cuerpo["status"] == "ok" and cuerpo["month_messages"] == 3
    with db() as session:
        assert month_usage(session, bot_id).total == 3


@pytest.mark.parametrize("cambios", [{"received": -1}, {"sent": -1}, {"received": 101}, {"sent": 101}, {"number_id": ""}])
def test_un_cuerpo_invalido_de_mensajes_responde_422(client, db, mundo, servicio, cambios):
    _bot(db, mundo["artefacto"].id)
    cuerpo = {"number_id": NUMERO, "received": 1, "sent": 0, **cambios}
    assert client.post("/bot/messages", json=cuerpo, headers=servicio).status_code == 422


def test_un_numero_sin_bot_es_unknown_bot_y_no_suma_nada(client, db, mundo, servicio):
    cuerpo = _mensajes(client, servicio, received=1, number="000").json()

    assert cuerpo["status"] == "unknown_bot"
    assert cuerpo["month_messages"] is None and cuerpo["month_cap"] is None
    with db() as session:
        assert session.query(Bot).count() == 0
        from mia.storage.models import BotMessageCount

        assert session.query(BotMessageCount).count() == 0


def test_un_bot_desactivado_responde_disabled_y_aun_asi_cuenta_el_mensaje(client, db, mundo, servicio):
    bot_id = _bot(db, mundo["artefacto"].id, active=False)

    cuerpo = _mensajes(client, servicio, received=1).json()

    assert cuerpo["status"] == "disabled" and cuerpo["month_messages"] == 1
    with db() as session:
        assert month_usage(session, bot_id).received == 1


def test_un_bot_sin_artefacto_o_con_el_artefacto_desactivado_responde_disabled(client, db, mundo, servicio, make_artifact):
    _bot(db, None, number="1", name="Sin artefacto")
    apagado = make_artifact("Apagado", units=["u1"], active=False)
    _bot(db, apagado.id, number="2", name="Con artefacto apagado")

    assert _mensajes(client, servicio, number="1").json()["status"] == "disabled"
    assert _mensajes(client, servicio, number="2").json()["status"] == "disabled"


def test_al_llegar_al_tope_mensual_responde_cap_reached(client, db, mundo, servicio, monkeypatch):
    monkeypatch.setattr(settings, "bot_monthly_message_cap", 5)
    _bot(db, mundo["artefacto"].id)

    assert _mensajes(client, servicio, received=4).json()["status"] == "ok"
    quinto = _mensajes(client, servicio, received=1).json()

    assert quinto["status"] == "cap_reached"
    assert quinto["month_messages"] == 5 and quinto["month_cap"] == 5
    # Lo recibido después del tope se sigue contando (consume la cuota aunque no se responda).
    assert _mensajes(client, servicio, received=1).json()["month_messages"] == 6


def test_cap_reached_gana_sobre_disabled(client, db, mundo, servicio, monkeypatch):
    monkeypatch.setattr(settings, "bot_monthly_message_cap", 2)
    _bot(db, mundo["artefacto"].id, active=False)

    assert _mensajes(client, servicio, received=2).json()["status"] == "cap_reached"


def test_un_mes_nuevo_empieza_en_cero(client, db, mundo, servicio, monkeypatch):
    monkeypatch.setattr(settings, "bot_monthly_message_cap", 3)
    _bot(db, mundo["artefacto"].id)
    with patch("mia.api.routes.bot_service.current_month", return_value="2026-09"):
        assert _mensajes(client, servicio, received=3).json()["status"] == "cap_reached"

    cuerpo = _mensajes(client, servicio, received=1).json()

    assert cuerpo["status"] == "ok" and cuerpo["month_messages"] == 1 and cuerpo["month"] == current_month()


def test_el_consumo_de_un_bot_no_afecta_al_de_otro(client, db, mundo, servicio):
    _bot(db, mundo["artefacto"].id, number="1", name="Uno")
    _bot(db, mundo["artefacto"].id, number="2", name="Dos")

    _mensajes(client, servicio, received=5, number="1")

    assert _mensajes(client, servicio, number="2").json()["month_messages"] == 0


# --- POST /bot/query -------------------------------------------------------------------------------------------


def test_la_consulta_usa_el_artefacto_asignado_en_modo_literal_y_los_dominios_del_artefacto(client, db, mundo, servicio):
    _bot(db, mundo["artefacto"].id)

    with Pipeline() as pipeline:
        respuesta = _pregunta(client, servicio)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["answer"] == "La matrícula es del 3 al 7 de agosto." and cuerpo["mode"] == "literal"
    assert cuerpo["no_info"] is False and cuerpo["images"] == []
    assert cuerpo["sources"][0]["document"] == "requisitos.pdf"
    # Los dominios los decide la API: los de la unidad del artefacto, ordenados, no los que mande el servicio.
    assert pipeline.searched_domains == ["dom-1", "dom-2"]
    with db() as session:
        registro = session.query(QueryLog).one()
    assert registro.artifact_id == mundo["artefacto"].id
    assert registro.mode == "literal" and registro.outcome == "answered"
    assert registro.question == "¿Cuándo es la matrícula?"


def test_el_modo_es_siempre_literal_aunque_el_artefacto_permita_razonamiento(client, db, mundo, servicio):
    _bot(db, mundo["artefacto"].id)

    with Pipeline() as pipeline:
        _pregunta(client, servicio)

    # `get_llm_provider(proveedor, modelo, esfuerzo)` se pide con la configuración del modo literal.
    assert pipeline.get_llm.call_args.args[:2] == ("openrouter", "proveedor/modelo-literal")
    with db() as session:
        assert session.query(QueryLog).one().mode == "literal"


def test_el_registro_de_uso_no_tiene_ningun_telefono(client, db, mundo, servicio):
    """La API nunca recibe el teléfono de la persona: solo el `number_id` de la institución (FR-027, SC-010)."""
    _bot(db, mundo["artefacto"].id)

    with Pipeline():
        _pregunta(client, servicio)

    with db() as session:
        registro = session.query(QueryLog).one()
    for valor in (registro.question, registro.domain_ids, registro.sources, registro.reject_reason or ""):
        assert NUMERO not in valor
    # Y la ruta no acepta campos de teléfono: se ignoran, no se guardan.
    with Pipeline():
        client.post(
            "/bot/query",
            json={"number_id": NUMERO, "question": "otra", "phone": "50688887777", "from": "50688887777"},
            headers=servicio,
        )
    with db() as session:
        assert all("50688887777" not in (q.question + q.domain_ids + q.sources) for q in session.query(QueryLog))


def test_un_cambio_de_artefacto_asignado_rige_en_la_consulta_siguiente(client, db, mundo, servicio, make_artifact):
    bot_id = _bot(db, mundo["artefacto"].id)
    otro = make_artifact("Bot de Analítica", units=["u2"])

    with Pipeline() as pipeline:
        _pregunta(client, servicio)
        assert pipeline.searched_domains == ["dom-1", "dom-2"]
        with db() as session:
            session.get(Bot, bot_id).artifact_id = otro.id
            session.commit()
        _pregunta(client, servicio)
        assert pipeline.searched_domains == ["dom-3"]
    with db() as session:
        artefactos = [q.artifact_id for q in session.query(QueryLog).order_by(QueryLog.created_at)]
    assert artefactos == [mundo["artefacto"].id, otro.id]


def test_un_cambio_de_los_accesos_del_artefacto_rige_en_la_consulta_siguiente(client, db, mundo, servicio):
    _bot(db, mundo["artefacto"].id)

    with Pipeline() as pipeline:
        _pregunta(client, servicio)
        assert pipeline.searched_domains == ["dom-1", "dom-2"]
        with db() as session:
            session.add(ArtifactDomain(artifact_id=mundo["artefacto"].id, domain_id="dom-3"))
            session.commit()
        _pregunta(client, servicio)
        assert pipeline.searched_domains == ["dom-1", "dom-2", "dom-3"]


def test_un_bot_desactivado_responde_403_sin_consultar(client, db, mundo, servicio):
    _bot(db, mundo["artefacto"].id, active=False)

    with Pipeline() as pipeline:
        respuesta = _pregunta(client, servicio)

    assert respuesta.status_code == 403
    pipeline.store.search.assert_not_called()


def test_un_bot_sin_artefacto_responde_403(client, db, mundo, servicio):
    _bot(db, None)
    with Pipeline():
        assert _pregunta(client, servicio).status_code == 403


def test_un_artefacto_desactivado_responde_403_y_el_rechazo_queda_en_uso(client, db, mundo, servicio, make_artifact):
    apagado = make_artifact("Apagado", units=["u1"], active=False)
    _bot(db, apagado.id)

    with Pipeline() as pipeline:
        respuesta = _pregunta(client, servicio)

    assert respuesta.status_code == 403
    pipeline.store.search.assert_not_called()
    with db() as session:
        registro = session.query(QueryLog).one()
    assert registro.artifact_id == apagado.id and registro.outcome == "rejected_permission"


def test_si_el_artefacto_no_permite_el_modo_literal_responde_403(client, db, mundo, servicio, make_artifact):
    solo_razonamiento = make_artifact("Solo razonamiento", units=["u1"], modes="razonamiento")
    _bot(db, solo_razonamiento.id)

    with Pipeline():
        respuesta = _pregunta(client, servicio)

    assert respuesta.status_code == 403
    assert "literal" in respuesta.json()["detail"]


def test_un_numero_sin_bot_responde_404(client, db, mundo, servicio):
    with Pipeline() as pipeline:
        respuesta = _pregunta(client, servicio, number="000")
    assert respuesta.status_code == 404 and respuesta.json()["detail"] == "Bot no encontrado."
    pipeline.store.search.assert_not_called()


def test_el_tope_diario_del_artefacto_responde_429_con_retry_after(client, db, mundo, servicio):
    _bot(db, mundo["artefacto"].id)
    with db() as session:
        session.add(QueryLog(
            id=str(uuid.uuid4()), artifact_id=mundo["artefacto"].id, question="x", domain_ids="[]", mode="literal",
            outcome="answered", cost_usd=Decimal("1.5"),
        ))
        session.commit()

    with Pipeline() as pipeline:
        respuesta = _pregunta(client, servicio)

    assert respuesta.status_code == 429
    assert int(respuesta.headers["retry-after"]) > 0
    pipeline.store.search.assert_not_called()


def test_el_tope_del_bot_no_afecta_a_otro_artefacto(client, db, mundo, servicio, make_artifact):
    _bot(db, mundo["artefacto"].id)
    otro = make_artifact("Otro artefacto", units=["u1"], cap=1.0)
    with db() as session:
        session.add(QueryLog(
            id=str(uuid.uuid4()), artifact_id=mundo["artefacto"].id, question="x", domain_ids="[]", mode="literal",
            outcome="answered", cost_usd=Decimal("1.5"),
        ))
        session.commit()

    with Pipeline():
        assert _pregunta(client, servicio).status_code == 429
        propia = client.post("/query", json={"domains": ["dom-1"], "question": "hola"}, headers=otro.headers)

    assert propia.status_code == 200


def test_una_falla_del_proveedor_de_modelos_responde_502(client, db, mundo, servicio):
    _bot(db, mundo["artefacto"].id)

    with Pipeline() as pipeline:
        pipeline.llm.answer.side_effect = RuntimeError("proveedor caído")
        respuesta = _pregunta(client, servicio)

    assert respuesta.status_code == 502


def test_una_pregunta_sin_respuesta_en_los_documentos_es_no_info(client, db, mundo, servicio):
    _bot(db, mundo["artefacto"].id)

    with Pipeline() as pipeline:
        pipeline.store.search.return_value = []
        cuerpo = _pregunta(client, servicio).json()

    assert cuerpo["no_info"] is True and cuerpo["sources"] == [] and cuerpo["images"] == []


def test_un_artefacto_sin_dominios_cubiertos_responde_no_info_sin_buscar(client, db, mundo, servicio, make_artifact):
    sin_dominios = make_artifact("Unidad vacía", units=["u3"])
    _bot(db, sin_dominios.id)

    with Pipeline() as pipeline:
        respuesta = _pregunta(client, servicio)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["no_info"] is True and cuerpo["sources"] == [] and cuerpo["images"] == [] and cuerpo["mode"] == "literal"
    pipeline.store.search.assert_not_called()
    pipeline.llm.answer.assert_not_called()
    with db() as session:
        registro = session.query(QueryLog).one()
    assert registro.artifact_id == sin_dominios.id and registro.outcome == "no_info" and registro.cost_usd == 0


@pytest.mark.parametrize("pregunta", ["", "x" * 2001], ids=["vacia", "demasiado-larga"])
def test_una_pregunta_vacia_o_demasiado_larga_responde_422(client, db, mundo, servicio, pregunta):
    _bot(db, mundo["artefacto"].id)
    assert _pregunta(client, servicio, question=pregunta).status_code == 422


def test_la_consulta_del_bot_no_cambia_la_de_los_artefactos(client, db, mundo, servicio):
    _bot(db, mundo["artefacto"].id)

    with Pipeline():
        propia = client.post(
            "/query", json={"domains": ["dom-1"], "question": "hola"}, headers=mundo["artefacto"].headers
        )

    assert propia.status_code == 200
    assert set(propia.json()) == {"id", "answer", "sources", "mode", "latency_ms", "no_info", "images"}
    assert Artifact is not None  # el artefacto sigue pudiendo consultar directo, con su clave


# --- Aislamiento: el bot no afecta a los demás artefactos (historia 8) ------------------------------------------


def _consulta_directa(client, artefacto):
    return client.post("/query", json={"domains": ["dom-1"], "question": "hola"}, headers=artefacto.headers)


def test_con_el_tope_mensual_del_bot_alcanzado_los_demas_artefactos_siguen_consultando(client, db, mundo, servicio, make_artifact, monkeypatch):
    monkeypatch.setattr(settings, "bot_monthly_message_cap", 2)
    _bot(db, mundo["artefacto"].id)
    otro = make_artifact("Consulta administrativa", units=["u1"])
    assert _mensajes(client, servicio, received=2).json()["status"] == "cap_reached"

    with Pipeline():
        assert _pregunta(client, servicio).status_code == 200  # el tope mensual es de mensajes: la consulta aún se podría hacer
        assert _consulta_directa(client, otro).status_code == 200


def test_con_el_bot_desactivado_los_demas_artefactos_siguen_consultando(client, db, mundo, servicio, make_artifact):
    _bot(db, mundo["artefacto"].id, active=False)
    otro = make_artifact("Consulta administrativa", units=["u1"])

    with Pipeline():
        assert _pregunta(client, servicio).status_code == 403
        assert _consulta_directa(client, otro).status_code == 200
        # El artefacto del bot también sigue sirviendo a quien lo use directo: desactivar el bot no lo toca.
        assert _consulta_directa(client, mundo["artefacto"]).status_code == 200


def test_con_el_artefacto_del_bot_en_su_tope_diario_otro_artefacto_sigue_consultando(client, db, mundo, servicio, make_artifact):
    _bot(db, mundo["artefacto"].id)
    otro = make_artifact("Consulta administrativa", units=["u1"], cap=1.0)
    with db() as session:
        session.add(QueryLog(
            id=str(uuid.uuid4()), artifact_id=mundo["artefacto"].id, question="x", domain_ids="[]", mode="literal",
            outcome="answered", cost_usd=Decimal("1.5"),
        ))
        session.commit()

    with Pipeline():
        assert _pregunta(client, servicio).status_code == 429
        assert _consulta_directa(client, otro).status_code == 200


def test_los_mensajes_del_bot_no_suman_al_gasto_de_ningun_artefacto(client, db, mundo, servicio, admin):
    _bot(db, mundo["artefacto"].id)

    _mensajes(client, servicio, received=50, sent=50)

    artefactos = client.get("/artifacts", headers=admin).json()
    assert artefactos["global"]["spent_today_usd"] == 0
    assert all(a["today"]["spent_usd"] == 0 for a in artefactos["artifacts"])


def test_las_consultas_del_bot_cuentan_en_el_gasto_y_en_las_consultas_del_artefacto_asignado(client, db, mundo, servicio, admin):
    _bot(db, mundo["artefacto"].id)

    with Pipeline():
        _pregunta(client, servicio)
        _pregunta(client, servicio)

    artefacto = next(a for a in client.get("/artifacts", headers=admin).json()["artifacts"] if a["id"] == mundo["artefacto"].id)
    assert artefacto["queries_last_7_days"] == 2
    assert artefacto["today"]["spent_usd"] == pytest.approx(0.0008)
