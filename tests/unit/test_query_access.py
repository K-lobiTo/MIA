import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select

from mia.api.routes import query as query_routes
from mia.api.routes.query import NO_INFO_ANSWER
from mia.config import settings
from mia.rag.llm import LLMAnswer
from mia.storage.models import Document, Domain, QueryLog, Unit
from mia.storage.vector_store import SearchResult


@pytest.fixture
def base(db, modes_config, monkeypatch):
    monkeypatch.setattr(settings, "query_similarity_threshold", 0.5)
    with db() as session:
        session.add_all([Unit(id="u1", name="Computación"), Unit(id="u2", name="Administración de Empresas")])
        session.flush()
        session.add_all(
            [
                Domain(id="d1", unit_id="u1", name="Memoria del Consejo"),
                Domain(id="d2", unit_id="u2", name="Memoria del Consejo"),
            ]
        )
        session.flush()
        session.add(Document(id="doc-1", domain_id="d1", filename="acta.pdf", source_type="pdf", file_hash="h", status="done"))
        session.commit()


@pytest.fixture
def fakes():
    """Búsqueda, embeddings y LLM falsos. `llm.answer` se puede reconfigurar en cada prueba."""
    vector_store = MagicMock()
    vector_store.count_chunks.return_value = 100
    vector_store.search.return_value = [
        SearchResult(chunk_id="c1", document_id="doc-1", domain="d1", text="fragmento relevante", score=0.9)
    ]
    embeddings = MagicMock()
    embeddings.embed.return_value = [[0.1, 0.2]]
    llm = MagicMock()
    llm.answer.return_value = LLMAnswer(
        text="Respuesta con fuente.", model="proveedor/modelo-literal",
        prompt_tokens=1200, completion_tokens=80, reasoning_tokens=30, cost_usd=0.0042,
    )
    get_llm = MagicMock(return_value=llm)
    with (
        patch.object(query_routes, "get_vector_store", return_value=vector_store),
        patch.object(query_routes, "get_embedding_provider", return_value=embeddings),
        patch.object(query_routes, "get_llm_provider", get_llm),
    ):
        yield SimpleNamespaceFakes(vector_store, embeddings, llm, get_llm)


class SimpleNamespaceFakes:
    def __init__(self, vector_store, embeddings, llm, get_llm):
        self.vector_store, self.embeddings, self.llm, self.get_llm = vector_store, embeddings, llm, get_llm


def _consultar(client, headers=None, domains=("d1",), mode=None, question="¿Qué se acordó?"):
    cuerpo = {"domains": list(domains), "question": question}
    if mode:
        cuerpo["mode"] = mode
    return client.post("/query", json=cuerpo, headers=headers or {})


def _registros(db):
    with db() as session:
        return list(session.scalars(select(QueryLog).order_by(QueryLog.created_at)))


def test_sin_clave_o_con_clave_invalida_responde_401_y_no_registra(client, db, base, fakes):
    assert _consultar(client).status_code == 401
    assert _consultar(client, {"X-Artifact-Key": "mia_falsa"}).status_code == 401
    assert _registros(db) == []
    fakes.llm.answer.assert_not_called()


def test_consulta_valida_responde_y_registra_todo(client, db, base, fakes, make_artifact):
    artefacto = make_artifact(units=["u1"])

    response = _consultar(client, artefacto.headers)

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Respuesta con fuente." and body["mode"] == "literal"
    assert body["id"] and isinstance(body["latency_ms"], int) and body["latency_ms"] >= 0
    assert body["sources"] == [{"domain": "Memoria del Consejo", "document": "acta.pdf", "excerpt": "fragmento relevante"}]
    [registro] = _registros(db)
    assert registro.id == body["id"] and registro.artifact_id == artefacto.id
    assert registro.question == "¿Qué se acordó?" and json.loads(registro.domain_ids) == ["d1"]
    assert registro.mode == "literal" and registro.model == "proveedor/modelo-literal"
    assert (registro.prompt_tokens, registro.completion_tokens, registro.reasoning_tokens) == (1200, 80, 30)
    assert registro.cost_usd == Decimal("0.0042") and registro.cost_estimated is False
    assert registro.outcome == "answered" and registro.reject_reason is None
    assert registro.latency_ms == body["latency_ms"]
    assert json.loads(registro.sources) == [{"domain": "Memoria del Consejo", "document": "acta.pdf"}]


def test_sin_costo_del_proveedor_se_estima_con_los_precios_del_modo(client, db, base, fakes, make_artifact, monkeypatch):
    monkeypatch.setattr(settings, "llm_price_in_literal", 2.0)  # USD por millón de tokens
    monkeypatch.setattr(settings, "llm_price_out_literal", 10.0)
    fakes.llm.answer.return_value = LLMAnswer(text="Respuesta.", model="m", prompt_tokens=1_000_000, completion_tokens=100_000)
    artefacto = make_artifact(units=["u1"])

    _consultar(client, artefacto.headers)

    [registro] = _registros(db)
    assert registro.cost_usd == Decimal("3.000000") and registro.cost_estimated is True


def test_artefacto_desactivado_responde_403_y_lo_registra(client, db, base, fakes, make_artifact):
    artefacto = make_artifact(units=["u1"], active=False)

    response = _consultar(client, artefacto.headers)

    assert response.status_code == 403 and "desactivado" in response.json()["detail"]
    [registro] = _registros(db)
    assert registro.outcome == "rejected_permission" and registro.cost_usd == 0
    assert "desactivado" in registro.reject_reason
    fakes.llm.answer.assert_not_called()


def test_dominio_no_permitido_responde_403(client, db, base, fakes, make_artifact):
    artefacto = make_artifact(units=["u1"])  # solo Computación

    response = _consultar(client, artefacto.headers, domains=("d1", "d2"))

    assert response.status_code == 403 and "d2" in response.json()["detail"]
    [registro] = _registros(db)
    assert registro.outcome == "rejected_permission"
    fakes.vector_store.search.assert_not_called()


def test_cada_instancia_solo_consulta_los_dominios_de_su_unidad(client, db, base, fakes, make_artifact):
    computacion = make_artifact("Consulta Computación", units=["u1"])
    administracion = make_artifact("Consulta Administración", units=["u2"])

    assert _consultar(client, computacion.headers, domains=("d1",)).status_code == 200
    assert _consultar(client, computacion.headers, domains=("d2",)).status_code == 403
    assert _consultar(client, administracion.headers, domains=("d1",)).status_code == 403
    assert _consultar(client, administracion.headers, domains=("d2",)).status_code == 200


def test_modo_no_permitido_al_artefacto_responde_403(client, db, base, fakes, make_artifact):
    artefacto = make_artifact(units=["u1"], modes="literal")

    response = _consultar(client, artefacto.headers, mode="razonamiento")

    assert response.status_code == 403 and "razonamiento" in response.json()["detail"]
    assert _registros(db)[0].outcome == "rejected_permission"


def test_modo_no_disponible_en_la_instancia_responde_403(client, db, base, fakes, make_artifact, monkeypatch):
    monkeypatch.setattr(settings, "llm_provider_razonamiento", "")
    artefacto = make_artifact(units=["u1"], modes="literal,razonamiento")

    assert _consultar(client, artefacto.headers, mode="razonamiento").status_code == 403


def test_modo_desconocido_responde_422(client, base, fakes, make_artifact):
    artefacto = make_artifact(units=["u1"])
    assert _consultar(client, artefacto.headers, mode="inventado").status_code == 422


def test_cada_modo_usa_su_proveedor_modelo_y_esfuerzo(client, base, fakes, make_artifact):
    artefacto = make_artifact(units=["u1"], modes="literal,razonamiento")

    _consultar(client, artefacto.headers)
    assert fakes.get_llm.call_args.args == ("openrouter", "proveedor/modelo-literal", "low")
    body = _consultar(client, artefacto.headers, mode="razonamiento").json()
    assert fakes.get_llm.call_args.args == ("openrouter", "proveedor/modelo-razonamiento", "high")
    assert body["mode"] == "razonamiento"


def test_sin_resultados_relevantes_registra_sin_informacion_y_costo_cero(client, db, base, fakes, make_artifact):
    fakes.vector_store.search.return_value = [
        SearchResult(chunk_id="c1", document_id="doc-1", domain="d1", text="otro tema", score=0.1)
    ]
    artefacto = make_artifact(units=["u1"])

    body = _consultar(client, artefacto.headers).json()

    assert body["answer"] == NO_INFO_ANSWER and body["sources"] == []
    [registro] = _registros(db)
    assert registro.outcome == "no_info" and registro.cost_usd == 0 and registro.model is None
    fakes.llm.answer.assert_not_called()


def test_si_el_llm_indica_sin_informacion_se_registra_su_costo(client, db, base, fakes, make_artifact):
    fakes.llm.answer.return_value = LLMAnswer(text=" SIN_INFORMACION.\n", model="m", prompt_tokens=900, completion_tokens=5, cost_usd=0.001)
    artefacto = make_artifact(units=["u1"])

    body = _consultar(client, artefacto.headers).json()

    assert body["answer"] == NO_INFO_ANSWER and body["sources"] == []
    [registro] = _registros(db)
    assert registro.outcome == "no_info" and registro.cost_usd == Decimal("0.001") and registro.prompt_tokens == 900


def test_fallo_del_proveedor_responde_502_y_se_registra_como_error(client, db, base, fakes, make_artifact):
    fakes.llm.answer.side_effect = RuntimeError("saldo agotado")
    artefacto = make_artifact(units=["u1"])

    response = _consultar(client, artefacto.headers)

    assert response.status_code == 502
    [registro] = _registros(db)
    assert registro.outcome == "error" and registro.cost_usd == 0 and "saldo agotado" in (registro.reject_reason or "")


def test_calificar_una_consulta(client, db, base, fakes, make_artifact):
    artefacto = make_artifact(units=["u1"])
    consulta = _consultar(client, artefacto.headers).json()

    response = client.post(
        f"/query/{consulta['id']}/feedback", json={"rating": "util", "comment": "Justo lo que necesitaba"}, headers=artefacto.headers
    )

    assert response.status_code == 204
    [registro] = _registros(db)
    assert registro.rating == "util" and registro.rating_comment == "Justo lo que necesitaba"


def test_una_segunda_calificacion_reemplaza_la_anterior(client, db, base, fakes, make_artifact):
    artefacto = make_artifact(units=["u1"])
    consulta = _consultar(client, artefacto.headers).json()
    url = f"/query/{consulta['id']}/feedback"

    client.post(url, json={"rating": "util", "comment": "bien"}, headers=artefacto.headers)
    client.post(url, json={"rating": "no_util"}, headers=artefacto.headers)

    [registro] = _registros(db)
    assert registro.rating == "no_util" and registro.rating_comment is None


def test_no_se_califica_una_consulta_de_otro_artefacto_ni_inexistente(client, db, base, fakes, make_artifact):
    uno = make_artifact("Uno", units=["u1"])
    otro = make_artifact("Otro", units=["u1"])
    consulta = _consultar(client, uno.headers).json()

    assert client.post(f"/query/{consulta['id']}/feedback", json={"rating": "util"}, headers=otro.headers).status_code == 404
    assert client.post("/query/no-existe/feedback", json={"rating": "util"}, headers=uno.headers).status_code == 404
    assert client.post(f"/query/{consulta['id']}/feedback", json={"rating": "util"}).status_code == 401
    assert client.post(f"/query/{consulta['id']}/feedback", json={"rating": "regular"}, headers=uno.headers).status_code == 422
