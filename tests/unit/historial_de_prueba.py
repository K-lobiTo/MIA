"""El mundo simulado de las pruebas de la memoria de conversación (feature 014): un artefacto con dominios, un almacén cuya
búsqueda depende del tema que nombra el texto del embedding, embeddings y modelo simulados. Los usan las pruebas de
`test_query_history*.py`."""

from unittest.mock import MagicMock, patch

from mia.api.routes import query as query_routes
from mia.config import settings
from mia.rag.llm import LLMAnswer
from mia.storage.models import Artifact, Document, Domain, Unit
from mia.storage.vector_store import SearchResult

ANALITICA = "analítica"
CIBERSEGURIDAD = "ciberseguridad"
NO_INFO_TEXTO = "No encontré información suficiente"


def crear_mundo(
    db,
    make_artifact,
    monkeypatch,
    *,
    context_turns=3,
    modes="literal,razonamiento",
    cap=1.0,
    reasoning_cap=None,
):
    """Un artefacto con los dominios de un programa y `context_turns` vueltas de memoria; devuelve el artefacto."""
    monkeypatch.setattr(settings, "query_context_neighbors", 0)
    with db() as session:
        session.add(Unit(id="u1", name="Computación"))
        session.flush()
        session.add(Domain(id="dom-1", unit_id="u1", name="Apertura de promoción"))
        session.flush()
        for doc in ("ana-admision", "ana-presentacion", "ciber-admision"):
            session.add(
                Document(
                    id=doc,
                    domain_id="dom-1",
                    filename=f"{doc}.txt",
                    source_type="txt",
                    file_hash=doc,
                    status="done",
                )
            )
        session.commit()
    artefacto = make_artifact(
        "Consulta", units=["u1"], modes=modes, cap=cap, reasoning_cap=reasoning_cap
    )
    fijar_memoria(db, artefacto.id, context_turns)
    return artefacto


def fijar_memoria(db, artifact_id, context_turns):
    with db() as session:
        session.get(Artifact, artifact_id).context_turns = context_turns
        session.commit()


class Pipeline:
    """Almacén, embeddings y modelo simulados. El tema de la pregunta (el vector) sale del texto con que se calcula el
    embedding: si nombra "analítica" la búsqueda devuelve los documentos de Analítica; si nombra "ciberseguridad", los de
    Ciberseguridad; si no, nada (como un seguimiento corto sin contexto). `textos` guarda los textos embebidos."""

    def __init__(
        self, respuesta="El costo es de ₡61 000 por crédito.", costo=0.0004, tokens=(1000, 50)
    ):
        self.textos: list[str] = []
        self.store = MagicMock()
        self.store.count_chunks.return_value = 100
        self.store.get_chunks.return_value = []
        self.store.search.side_effect = self._buscar
        self.embeddings = MagicMock()
        self.embeddings.embed.side_effect = self._embeber
        self.llm = MagicMock()
        self.llm.answer.return_value = LLMAnswer(
            text=respuesta,
            model="modelo",
            prompt_tokens=tokens[0],
            completion_tokens=tokens[1],
            cost_usd=costo,
        )
        self.get_llm = MagicMock(return_value=self.llm)

    def _embeber(self, textos, is_query=False):
        self.textos.extend(textos)
        salida = []
        for texto in textos:
            bajo = texto.lower()
            tema = 2.0 if ANALITICA in bajo else 1.0 if CIBERSEGURIDAD in bajo else 0.0
            salida.append([tema, 0.0])
        return salida

    def _buscar(self, vector, domains, limit):
        def resultado(documento):
            return SearchResult(
                chunk_id=f"c-{documento}",
                document_id=documento,
                domain="dom-1",
                text="fragmento",
                score=0.95,
            )

        if vector[0] == 2.0:
            return [resultado("ana-admision"), resultado("ana-presentacion")]
        if vector[0] == 1.0:
            return [resultado("ciber-admision")]
        return []

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
    def historial_al_modelo(self):
        """El historial con que se llamó al modelo en la última respuesta (None si no se envió)."""
        return self.llm.answer.call_args.kwargs.get("history")


def preguntar(client, artefacto, pregunta, *, modo="literal", historial=None, dominios=("dom-1",)):
    cuerpo = {"domains": list(dominios), "question": pregunta, "mode": modo}
    if historial is not None:
        cuerpo["history"] = historial
    return client.post("/query", json=cuerpo, headers=artefacto.headers)


def vuelta(pregunta, respuesta, modo=None):
    v = {"question": pregunta, "answer": respuesta}
    if modo:
        v["mode"] = modo
    return v
