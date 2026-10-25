"""De punta a punta, en un solo proceso: el servicio del bot (paquete `mia_whatsapp`) llamando a la API real de MIA, con
Kapso simulado, el almacén de vectores y el modelo simulados y una base SQLite de prueba (feature 011).

Comprueba lo que ninguna de las dos mitades prueba sola: que el servicio y la API se entienden (rutas, credencial de
servicio, estados y forma de la respuesta), y que un cambio hecho en el panel rige en el mensaje siguiente.
"""

import asyncio
import json
import uuid
from unittest.mock import MagicMock, patch

import httpx
import pytest
from mia_whatsapp.api_client import MiaApiClient
from mia_whatsapp.config import Settings as BotSettings
from mia_whatsapp.flow import Deps, handle_message
from mia_whatsapp.kapso import KapsoClient
from mia_whatsapp.state import State
from mia_whatsapp.webhook import EVENT, parse_event

from mia.api.main import app
from mia.api.routes import query as query_routes
from mia.bots.usage import current_month, month_usage
from mia.config import settings
from mia.rag.llm import LLMAnswer
from mia.storage.models import Bot, Document, DocumentImage, Domain, QueryLog, Unit
from mia.storage.vector_store import SearchResult
from tests.unit.imagenes_de_prueba import PNG

CLAVE = "clave-de-servicio-de-prueba"
NUMERO = "647015955153740"
PUBLIC_ID = "e2e" + "x" * 29


class KapsoSimulado:
    def __init__(self):
        self.enviados: list[dict] = []

    def transport(self) -> httpx.MockTransport:
        def handler(request: httpx.Request) -> httpx.Response:
            self.enviados.append(json.loads(request.content))
            return httpx.Response(200, json={"messages": [{"id": "wamid.salida"}]})

        return httpx.MockTransport(handler)

    @property
    def textos(self) -> list[str]:
        return [m["text"]["body"] for m in self.enviados if m["type"] == "text"]

    @property
    def imagenes(self) -> list[dict]:
        return [m["image"] for m in self.enviados if m["type"] == "image"]


@pytest.fixture
def mundo(db, modes_config, make_artifact, monkeypatch):
    monkeypatch.setattr(settings, "bot_service_key", CLAVE)
    with db() as session:
        session.add_all([Unit(id="u1", name="Computación"), Unit(id="u2", name="Analítica")])
        session.flush()
        session.add_all([Domain(id="dom-1", unit_id="u1", name="Admisión"), Domain(id="dom-2", unit_id="u2", name="Costos")])
        session.flush()
        session.add_all([
            Document(id="doc-1", domain_id="dom-1", filename="horario_matricula.pdf", source_type="pdf", file_hash="h1", status="done"),
            Document(id="doc-2", domain_id="dom-2", filename="costos.pdf", source_type="pdf", file_hash="h2", status="done"),
        ])
        session.flush()
        session.add(DocumentImage(
            id="img-1", document_id="doc-1", public_id=PUBLIC_ID, content_type="image/png", content=PNG,
            size_bytes=len(PNG), caption="Horario de matrícula", position=0, created_by="automatizacion",
        ))
        session.commit()
    computacion = make_artifact("Bot de Computación", units=["u1"], modes="literal,razonamiento")
    analitica = make_artifact("Bot de Analítica", units=["u2"])
    bot_id = str(uuid.uuid4())
    with db() as session:
        session.add(Bot(id=bot_id, name="Atracción de estudiantes", kapso_number_id=NUMERO, artifact_id=computacion.id))
        session.commit()
    return {"bot_id": bot_id, "computacion": computacion, "analitica": analitica}


class Servicio:
    """El servicio del bot conectado a la API real (sin red) y a un Kapso simulado."""

    def __init__(self, **ajustes):
        valores = {
            "mia_api_url": "https://mia.example.com",
            "bot_service_key": CLAVE,
            "kapso_api_key": "clave-de-kapso",
            "kapso_webhook_secret": "secreto",
            **ajustes,
        }
        self.settings = BotSettings(_env_file=None, **valores)
        self.kapso = KapsoSimulado()
        self.deps = Deps(
            settings=self.settings,
            state=State(self.settings),
            api=MiaApiClient(self.settings, httpx.AsyncClient(transport=httpx.ASGITransport(app=app))),
            kapso=KapsoClient(self.settings, httpx.AsyncClient(transport=self.kapso.transport())),
        )
        self._n = 0

    def escribir(self, texto: str | None = "¿Cuándo es la matrícula?", *, persona="ana", tipo="text", numero=NUMERO):
        """Una persona escribe al bot: el aviso de Kapso pasa por la lectura real del webhook y por el flujo del bot."""
        self._n += 1
        aviso = {
            "message": {
                "id": f"wamid.e2e.{self._n}", "type": tipo, "from": f"506{abs(hash(persona)) % 10**8:08d}",
                **({"text": {"body": texto}} if tipo == "text" else {}),
            },
            "conversation": {"id": f"conv-{persona}", "phone_number_id": numero},
            "phone_number_id": numero,
        }
        mensajes = parse_event({"x-webhook-event": EVENT}, json.dumps(aviso).encode()).messages
        for mensaje in mensajes:
            asyncio.run(handle_message(mensaje, self.deps))


class Pipeline:
    def __init__(self, texto="Es del 3 al 7 de agosto.\nFUENTES: 1", documento=1, dominios_vistos=None):
        self.store = MagicMock()
        self.store.count_chunks.return_value = 100
        self.store.get_chunks.return_value = []
        self.store.search.side_effect = lambda vector, domains, limit: [
            SearchResult(
                chunk_id="c1", document_id="doc-1" if "dom-1" in domains else "doc-2", domain=domains[0],
                text="fragmento relevante", score=0.9,
            )
        ]
        self.embeddings = MagicMock()
        self.embeddings.embed.return_value = [[0.1, 0.2]]
        self.llm = MagicMock()
        self.llm.answer.return_value = LLMAnswer(text=texto, model="modelo", cost_usd=0.0004)

    def __enter__(self):
        self._p = [
            patch.object(settings, "query_cited_sources", "on"),
            patch.object(settings, "query_context_neighbors", 0),
            patch.object(query_routes, "get_vector_store", return_value=self.store),
            patch.object(query_routes, "get_embedding_provider", return_value=self.embeddings),
            patch.object(query_routes, "get_llm_provider", return_value=self.llm),
        ]
        for p in self._p:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in self._p:
            p.stop()


def test_una_pregunta_llega_a_la_api_y_la_persona_recibe_texto_fuentes_e_imagen(client, db, mundo):
    servicio = Servicio()

    with Pipeline():
        servicio.escribir()

    assert len(servicio.kapso.textos) == 1
    texto = servicio.kapso.textos[0]
    assert texto.startswith("Hola, soy un asistente automático") and "Es del 3 al 7 de agosto." in texto
    assert texto.endswith("Fuentes: horario_matricula.pdf")
    # La imagen sale con el enlace público de la API y su descripción como pie de foto...
    assert servicio.kapso.imagenes == [
        {"link": f"https://mia.example.com/media/{PUBLIC_ID}", "caption": "Horario de matrícula"}
    ]
    # ...y ese enlace sirve de verdad la imagen, sin ninguna credencial.
    servida = client.get(f"/media/{PUBLIC_ID}")
    assert servida.status_code == 200 and servida.content == PNG
    # La cuota del mes quedó contada en la base: 1 recibido, 2 enviados (el texto y la imagen).
    with db() as session:
        uso = month_usage(session, mundo["bot_id"], current_month())
        registro = session.query(QueryLog).one()
    assert (uso.received, uso.sent) == (1, 2)
    assert registro.artifact_id == mundo["computacion"].id and registro.mode == "literal" and registro.outcome == "answered"


def test_el_registro_de_uso_no_guarda_ningun_dato_de_la_persona(db, mundo):
    servicio = Servicio()

    with Pipeline():
        servicio.escribir("¿Cuándo es la matrícula?", persona="ana")

    with db() as session:
        registro = session.query(QueryLog).one()
    todo = " ".join([registro.question, registro.domain_ids, registro.sources, registro.reject_reason or ""])
    assert "506" not in todo and "conv-ana" not in todo and "wamid" not in todo


def test_una_pregunta_sin_respuesta_en_los_documentos_recibe_el_texto_sin_informacion_sin_imagen(db, mundo):
    servicio = Servicio()

    with Pipeline("SIN_INFORMACION"):
        servicio.escribir("¿Cuánto cuesta la luna?")

    assert servicio.kapso.imagenes == []
    assert "No encontré esa información en los documentos" in servicio.kapso.textos[0]


def test_cambiar_el_artefacto_del_bot_desde_el_panel_cambia_lo_que_responde_en_el_mensaje_siguiente(client, db, mundo, admin):
    servicio = Servicio()

    with Pipeline() as pipeline:
        servicio.escribir(persona="ana")
        assert pipeline.store.search.call_args.kwargs["domains"] == ["dom-1"]
        # El administrador cambia el artefacto asignado desde el panel (PATCH /bots), sin reiniciar nada.
        cambio = client.patch(f"/bots/{mundo['bot_id']}", json={"artifact_id": mundo["analitica"].id}, headers=admin)
        assert cambio.status_code == 200
        servicio.escribir(persona="ana")
        assert pipeline.store.search.call_args.kwargs["domains"] == ["dom-2"]

    with db() as session:
        artefactos = [q.artifact_id for q in session.query(QueryLog).order_by(QueryLog.created_at)]
    assert artefactos == [mundo["computacion"].id, mundo["analitica"].id]
    # El documento del segundo artefacto no tiene imágenes: la segunda respuesta va solo en texto.
    assert len(servicio.kapso.imagenes) == 1


def test_desactivar_el_bot_desde_el_panel_responde_no_disponible_y_el_artefacto_sigue_activo(client, db, mundo, admin):
    servicio = Servicio()
    client.patch(f"/bots/{mundo['bot_id']}", json={"active": False}, headers=admin)

    with Pipeline() as pipeline:
        servicio.escribir()
        consulta_directa = client.post(
            "/query", json={"domains": ["dom-1"], "question": "hola"}, headers=mundo["computacion"].headers
        )

    assert "Ahora mismo no puedo responder" in servicio.kapso.textos[0]
    pipeline.store.search.assert_called_once()  # solo la consulta directa del artefacto, no la del bot
    assert consulta_directa.status_code == 200


def test_con_el_tope_mensual_de_la_api_alcanzado_el_bot_no_envia_nada_y_el_panel_lo_muestra(client, db, mundo, admin, monkeypatch):
    monkeypatch.setattr(settings, "bot_monthly_message_cap", 3)
    servicio = Servicio()

    with Pipeline():
        servicio.escribir(persona="ana")   # recibido 1, enviados 2 (texto e imagen): llega a 3
        enviados = len(servicio.kapso.enviados)
        servicio.escribir(persona="beto")  # el tope ya está alcanzado: ni siquiera se consulta

    assert enviados == 2 and len(servicio.kapso.enviados) == 2
    bot = client.get("/bots", headers=admin).json()["bots"][0]
    assert bot["usage"]["cap_reached"] is True and bot["available"] is False
    assert bot["usage"]["received"] == 2 and bot["usage"]["sent"] == 2


def test_un_numero_sin_bot_registrado_se_ignora(db, mundo):
    servicio = Servicio()

    with Pipeline() as pipeline:
        servicio.escribir(numero="999999")

    assert servicio.kapso.enviados == []
    pipeline.store.search.assert_not_called()


def test_con_la_credencial_de_servicio_equivocada_el_bot_no_responde_nada(db, mundo):
    servicio = Servicio(bot_service_key="otra-clave")

    with Pipeline() as pipeline:
        servicio.escribir()

    assert servicio.kapso.enviados == []
    pipeline.store.search.assert_not_called()


def test_el_audio_y_la_pregunta_larga_no_llegan_al_modelo(db, mundo):
    servicio = Servicio()

    with Pipeline() as pipeline:
        servicio.escribir(None, tipo="audio", persona="ana")
        servicio.escribir("a" * 501, persona="beto")

    pipeline.llm.answer.assert_not_called()
    assert "solo entiendo mensajes de texto" in servicio.kapso.textos[0]
    assert "muy largo" in servicio.kapso.textos[1]
