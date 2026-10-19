"""LocalRerankProvider (feature 009) con una sesión y un tokenizador simulados: sin cargar el modelo real."""

import numpy as np
import pytest

from mia.config import settings
from mia.rag.providers.local_rerank import MAX_TOKENS, LocalRerankProvider
from mia.rag.rerank import RerankTimeout


class _Tokenizador:
    """Cada palabra es un id: 'a' -> 10, 'b' -> 11...; '?' -> 0 (desconocido)."""

    def encode(self, texto):
        return [0 if palabra == "?" else 10 + (ord(palabra[0]) - ord("a")) for palabra in texto.split()]


class _Sesion:
    def __init__(self, nombres=("input_ids", "attention_mask")):
        self.llamadas = []
        self._nombres = nombres

    def get_inputs(self):
        return [type("I", (), {"name": n})() for n in self._nombres]

    def run(self, _salidas, entradas):
        self.llamadas.append({k: v.copy() for k, v in entradas.items()})
        # Logit = suma de los ids reales del par, para reconocer el orden de salida.
        ids, mascara = entradas["input_ids"], entradas["attention_mask"]
        return [np.array([[float((ids[i] * mascara[i]).sum())] for i in range(len(ids))])]


@pytest.fixture
def proveedor():
    return LocalRerankProvider(session=_Sesion(), tokenizer=_Tokenizador())


def test_el_par_de_ids_tiene_el_formato_del_cross_encoder(proveedor):
    # Pregunta "a b" -> ids 10, 11 -> desplazados 11, 12. Pasaje "c ?" -> 12, 0 -> 13 y UNK (3).
    ids = proveedor._pair_ids(proveedor._pieces("a b"), "c ?")
    assert ids == [0, 11, 12, 2, 2, 13, 3, 2]


def test_el_pasaje_se_trunca_a_los_tokens_configurados(proveedor, monkeypatch):
    monkeypatch.setattr(settings, "rerank_passage_tokens", 32)
    pasaje = " ".join(["c"] * 100)
    ids = proveedor._pair_ids(proveedor._pieces("a"), pasaje)
    assert len(ids) == 1 + 1 + 2 + 32 + 1


def test_el_total_nunca_supera_el_maximo(proveedor, monkeypatch):
    monkeypatch.setattr(settings, "rerank_passage_tokens", 480)
    pregunta = " ".join(["a"] * 300)
    pasaje = " ".join(["c"] * 600)
    query = proveedor._pieces(pregunta)[: MAX_TOKENS // 2]
    assert len(proveedor._pair_ids(query, pasaje)) <= MAX_TOKENS


def test_entradas_del_grafo_y_lotes_de_cuatro():
    sesion = _Sesion()
    proveedor = LocalRerankProvider(session=sesion, tokenizer=_Tokenizador())
    pasajes = ["c", "d d", "e e e", "f", "g g"]
    logits = proveedor.score("a", pasajes)
    assert len(logits) == 5
    assert len(sesion.llamadas) == 2  # lotes de 4 y 1
    primera = sesion.llamadas[0]
    assert set(primera) == {"input_ids", "attention_mask"}  # sin token_type_ids
    assert primera["input_ids"].shape == (4, 8)  # el par más largo: 1 + 1 + 2 + 3 + 1
    # Relleno con PAD (1) y máscara de atención en 0 en el relleno.
    assert primera["input_ids"][0, -1] == 1 and primera["attention_mask"][0, -1] == 0
    assert primera["attention_mask"][2].sum() == 8


def test_el_orden_de_salida_es_el_de_entrada():
    proveedor = LocalRerankProvider(session=_Sesion(), tokenizer=_Tokenizador())
    # Logit = suma de ids: un pasaje más largo suma más. Se pasan en orden creciente y decreciente.
    creciente = proveedor.score("a", ["c", "c c", "c c c", "c c c c", "c c c c c"])
    assert creciente == sorted(creciente)
    decreciente = proveedor.score("a", ["c c c c c", "c c c c", "c c c", "c c", "c"])
    assert decreciente == sorted(decreciente, reverse=True)


def test_token_type_ids_solo_si_el_grafo_lo_pide():
    sesion = _Sesion(nombres=("input_ids", "attention_mask", "token_type_ids"))
    LocalRerankProvider(session=sesion, tokenizer=_Tokenizador()).score("a", ["c"])
    assert "token_type_ids" in sesion.llamadas[0]


def test_una_lista_vacia_no_llama_a_la_sesion():
    sesion = _Sesion()
    assert LocalRerankProvider(session=sesion, tokenizer=_Tokenizador()).score("a", []) == []
    assert sesion.llamadas == []


def test_con_el_tiempo_vencido_lanza_antes_del_segundo_lote_pero_puntua_el_primero():
    sesion = _Sesion()
    proveedor = LocalRerankProvider(session=sesion, tokenizer=_Tokenizador())
    with pytest.raises(RerankTimeout):
        proveedor.score("a", ["c"] * 8, deadline=0.0)
    assert len(sesion.llamadas) == 1  # el primer lote se permite
    # Un solo lote nunca lanza aunque el tiempo esté vencido, y sin deadline no lanza.
    assert len(proveedor.score("a", ["c"] * 4, deadline=0.0)) == 4
    assert len(proveedor.score("a", ["c"] * 8, deadline=None)) == 8
