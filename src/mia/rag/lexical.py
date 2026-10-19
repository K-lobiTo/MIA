"""Búsqueda por palabras (feature 010): normalización, grupos de la pregunta, regla de la mayoría y fusión con
la búsqueda por significado.

El módulo es puro: no importa Qdrant ni hace red. El almacén (`mia.storage.vector_store`) le da los fragmentos que
contienen cada palabra y esta lógica decide cuáles pasan al modelo de lenguaje. Se enciende con
QUERY_HYBRID_SEARCH=on y un fallo nunca rompe una consulta: la ruta cae a la búsqueda por significado.

Ver specs/010-busqueda-hibrida/contracts/busqueda-hibrida.md.
"""

import logging
import math
import re
import time
import unicodedata
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace

from mia.rag.completeness import switch_enabled
from mia.storage.vector_store import SearchResult

logger = logging.getLogger(__name__)

_WORD = re.compile(r"[a-z0-9]+")
# Una sigla escrita con puntos ("T.F.G.", "t.f.g"): letras sueltas separadas por puntos.
_DOTTED_ACRONYM = re.compile(r"\b[a-z](?:\.[a-z])+\b\.?")

# Palabras vacías en español, ya sin tildes: artículos, preposiciones, conjunciones, pronombres, interrogativos y
# verbos de pregunta. No incluye palabras de dominio ("maestria", "curso"): esas se descartan por frecuencia.
STOPWORDS = frozenset(
    ["a", "al", "algo", "alguien", "algun", "alguna", "algunas", "alguno", "algunos", "ante", "antes", "aqui", "asi", "aun", "aunque", "bajo", "cada", "casi", "como", "con", "contra", "cual", "cuales", "cuando", "cuanta", "cuantas", "cuanto", "cuantos", "cuyo", "cuya", "de", "del", "dentro", "desde", "donde", "dos", "durante", "el", "ella", "ellas", "ellos", "en", "entre", "eres", "es", "esa", "esas", "ese", "eso", "esos", "esta", "estan", "estar", "estas", "este", "esto", "estos", "fue", "fueron", "ha", "han", "hay", "hace", "hacer", "hasta", "he", "hemos", "la", "las", "le", "les", "lo", "los", "mas", "me", "mediante", "menos", "mi", "mis", "mismo", "misma", "mucho", "muy", "nada", "ni", "ningun", "ninguna", "no", "nos", "nosotros", "o", "os", "otra", "otras", "otro", "otros", "para", "pero", "poco", "por", "porque", "pues", "puede", "pueden", "que", "quien", "quienes", "quiero", "quisiera", "se", "segun", "ser", "si", "sido", "sin", "sobre", "solo", "son", "soy", "su", "sus", "tambien", "tampoco", "tan", "tanto", "te", "tener", "tengo", "tiene", "tienen", "todo", "toda", "todas", "todos", "tras", "tu", "tus", "un", "una", "uno", "unos", "usted", "ustedes", "va", "vamos", "van", "y", "ya", "yo", "dime", "dame", "cuentame", "hablame", "decir", "explicar", "explicame", "informacion", "datos", "favor", "saber", "sabe", "sabes", "sabemos", "ofrece", "ofrecen", "existe", "existen", "discutio", "discutieron", "acordo", "acordaron", "aprobo", "aprobaron"]
)


def hybrid_enabled(value: str) -> bool:
    """Si la búsqueda híbrida está encendida. Un valor inválido se trata como apagado y avisa una vez."""
    return switch_enabled(value, "QUERY_HYBRID_SEARCH")


def normalize(text: str) -> str:
    """Minúsculas y sin tildes; una sigla con puntos ("T.F.G.") pasa a "tfg"."""
    decomposed = unicodedata.normalize("NFD", (text or "").lower())
    plain = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    return _DOTTED_ACRONYM.sub(lambda m: m.group(0).replace(".", ""), plain)


def words_of(text: str) -> list[str]:
    """Las palabras (letras y dígitos) de un texto ya normalizado o por normalizar."""
    return _WORD.findall(normalize(text))


# --- Modelos ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Equivalence:
    """Una sigla y una de sus formas desarrolladas, ambas normalizadas."""

    sigla: str
    form: str


@dataclass(frozen=True)
class LexicalGroup:
    """Una palabra de la pregunta, o una sigla con su forma desarrollada, que se busca como un solo término."""

    terms: tuple[str, ...]
    chunk_ids: frozenset[str] = frozenset()
    specific: bool = False


@dataclass
class LexicalCandidate:
    chunk_id: str
    matched: int  # cuántos grupos específicos contiene
    weight: float  # suma del peso por rareza de esos grupos
    result: SearchResult | None = None


@dataclass
class LexicalOutcome:
    groups: list[LexicalGroup] = field(default_factory=list)
    specific: int = 0
    candidates: list[LexicalCandidate] = field(default_factory=list)
    elapsed_ms: int = 0  # lo que tardó el hilo léxico
    wait_ms: int = 0  # lo que la consulta esperó de más tras la búsqueda por significado, más la fusión
    failed: bool = False


# --- Grupos de la pregunta -----------------------------------------------------------------------


def query_groups(
    question: str, equivalences: Sequence[Equivalence], max_groups: int, min_len: int
) -> list[LexicalGroup]:
    """Las palabras de la pregunta como grupos de alternativas, en el orden de la pregunta.

    Se descartan las palabras vacías y las de menos de `min_len` letras. Una sigla de la lista de equivalencias
    lleva además sus formas desarrolladas, y una forma desarrollada que aparece como palabras consecutivas se
    reemplaza por un grupo con la forma y la sigla. Las equivalencias no se encadenan, y las alternativas que
    vienen de una equivalencia no se filtran por largo ni por palabra vacía."""
    words = words_of(question)
    forms_of: dict[str, list[str]] = {}
    for eq in equivalences:
        if eq.form not in forms_of.setdefault(eq.sigla, []):
            forms_of[eq.sigla].append(eq.form)

    # Formas desarrolladas presentes en la pregunta: posición inicial -> (largo en palabras, alternativas). Dos
    # formas que se solapan no se combinan: gana la que aparece primero en la lista.
    spans: dict[int, tuple[int, list[str]]] = {}
    covered: set[int] = set()
    for eq in equivalences:
        form_words = _WORD.findall(eq.form)
        size = len(form_words)
        if not size:
            continue
        for i in range(len(words) - size + 1):
            if words[i : i + size] != form_words:
                continue
            current = spans.get(i)
            if current is None and any(j in covered for j in range(i, i + size)):
                continue
            if current is not None and current[0] != size:
                continue
            alternatives = current[1] if current else []
            for term in (eq.form, eq.sigla):
                if term not in alternatives:
                    alternatives.append(term)
            spans[i] = (size, alternatives)
            covered.update(range(i, i + size))

    groups: list[tuple[str, ...]] = []
    i = 0
    while i < len(words):
        if i in spans:
            size, alternatives = spans[i]
            groups.append(tuple(alternatives))
            i += size
            continue
        word = words[i]
        i += 1
        if word in forms_of:
            groups.append((word, *forms_of[word]))
        elif len(word) >= min_len and word not in STOPWORDS:
            groups.append((word,))

    seen: set[tuple[str, ...]] = set()
    result: list[LexicalGroup] = []
    for terms in groups:
        if terms in seen:
            continue
        seen.add(terms)
        result.append(LexicalGroup(terms=terms))
        if len(result) >= max_groups:
            break
    return result


# --- Búsqueda en el almacén y regla de la mayoría ------------------------------------------------


def lexical_lookup(store, domains: list[str], groups: list[LexicalGroup], max_doc_freq: int,
                   executor: ThreadPoolExecutor | None = None) -> list[LexicalGroup]:
    """Los grupos con los fragmentos que contienen alguna de sus alternativas. Una consulta al almacén por
    alternativa, en paralelo, de a lo sumo `max_doc_freq + 1` fragmentos: pasar de `max_doc_freq` basta para saber que
    la palabra es común. Cualquier excepción del almacén sube sin capturarse."""
    if not groups:
        return []
    tasks = [(index, term) for index, group in enumerate(groups) for term in group.terms]

    def lookup(task):
        _, term = task
        return store.match_chunks(domains, term, max_doc_freq + 1)

    if executor is not None:
        found = list(executor.map(lookup, tasks))
    else:
        with ThreadPoolExecutor(max_workers=min(8, len(tasks))) as own:
            found = list(own.map(lookup, tasks))

    ids: list[set[str]] = [set() for _ in groups]
    for (index, _), chunk_ids in zip(tasks, found, strict=True):
        ids[index].update(chunk_ids)
    return [replace(group, chunk_ids=frozenset(chunk_ids)) for group, chunk_ids in zip(groups, ids, strict=True)]


def pick_candidates(groups: list[LexicalGroup], max_doc_freq: int, limit: int, elapsed_ms: int = 0) -> LexicalOutcome:
    """Regla de la mayoría: un grupo es específico si aparece en como máximo `max_doc_freq` fragmentos (uno que no
    aparece en ninguno cuenta como específico, sin coincidencias); con `n` grupos específicos, un fragmento pasa si
    contiene `n // 2 + 1` o más. Se ordena por grupos coincidentes y por peso (más peso cuanto más raro el grupo)."""
    marked = [replace(g, specific=len(g.chunk_ids) <= max_doc_freq) for g in groups]
    specific = [g for g in marked if g.specific]
    n = len(specific)
    if n == 0:
        return LexicalOutcome(groups=marked, specific=0, elapsed_ms=elapsed_ms)
    need = n // 2 + 1
    matched: dict[str, int] = {}
    weight: dict[str, float] = {}
    for group in specific:
        if not group.chunk_ids:
            continue
        group_weight = math.log(1 + (max_doc_freq + 1) / len(group.chunk_ids))
        for chunk_id in group.chunk_ids:
            matched[chunk_id] = matched.get(chunk_id, 0) + 1
            weight[chunk_id] = weight.get(chunk_id, 0.0) + group_weight
    candidates = [LexicalCandidate(chunk_id, count, weight[chunk_id]) for chunk_id, count in matched.items()
                  if count >= need]
    candidates.sort(key=lambda c: (-c.matched, -c.weight, c.chunk_id))
    return LexicalOutcome(groups=marked, specific=n, candidates=candidates[:limit], elapsed_ms=elapsed_ms)


def order_lexical(candidates: list[LexicalCandidate], scored: list[SearchResult]) -> list[SearchResult]:
    """Los resultados de los candidatos (con el coseno de la pregunta) en el orden léxico: más grupos coincidentes,
    más peso y, a igualdad, más coseno. Un candidato sin resultado (fuera de los dominios) se descarta."""
    by_id = {r.chunk_id: r for r in scored}
    ordered = [(c, by_id[c.chunk_id]) for c in candidates if c.chunk_id in by_id]
    ordered.sort(key=lambda pair: (-pair[0].matched, -pair[0].weight, -pair[1].score))
    return [result for _, result in ordered]


# --- Fusión ---------------------------------------------------------------------------------------


def merge_hybrid(vector_results: list[SearchResult], lexical_results: list[SearchResult], limit: int, slots: int,
                 k: int) -> list[SearchResult]:
    """Fusión por rango recíproco (RRF) de la lista de significado y la léxica. Los fragmentos que solo llegaron por
    palabras ocupan como mucho `slots` lugares y el total no supera `limit`. Sin candidatos léxicos devuelve la
    lista de significado tal cual; si actúa, cada resultado se devuelve en una copia cuyo `score` es el valor de
    fusión (sirve para ordenar, no se compara con el coseno)."""
    if not lexical_results:
        return vector_results
    fused: dict[str, float] = {}
    chosen: dict[str, SearchResult] = {}
    order: dict[str, int] = {}
    for rank, result in enumerate(vector_results, start=1):
        fused[result.chunk_id] = fused.get(result.chunk_id, 0.0) + 1.0 / (k + rank)
        chosen.setdefault(result.chunk_id, result)
        order.setdefault(result.chunk_id, len(order))
    only_lexical = 0
    for rank, result in enumerate(lexical_results, start=1):
        if result.chunk_id not in chosen:
            if only_lexical >= slots:
                continue
            only_lexical += 1
            chosen[result.chunk_id] = result
            order[result.chunk_id] = len(order)
        fused[result.chunk_id] = fused.get(result.chunk_id, 0.0) + 1.0 / (k + rank)
    ranked = sorted(chosen, key=lambda chunk_id: (-fused[chunk_id], order[chunk_id]))[:limit]
    return [replace(chosen[chunk_id], score=fused[chunk_id]) for chunk_id in ranked]


# --- Notas y avisos -------------------------------------------------------------------------------


def hybrid_note(outcome: LexicalOutcome, merged_new: int) -> str | None:
    """Nota de Uso con lo que aportó la parte léxica; None si no hubo candidatos."""
    if not outcome.candidates:
        return None
    return f"Búsqueda híbrida: {len(outcome.candidates)} por palabras, {merged_new} nuevos"


def failure_note() -> str:
    return "Búsqueda por palabras no disponible: se usó el significado"


_last_failure_warning: float | None = None
_WARNING_INTERVAL_SECONDS = 60.0


def _now() -> float:
    return time.monotonic()


def warn_lexical_failure(exc: Exception) -> None:
    """Aviso de un fallo de la parte léxica en una consulta: como máximo uno por minuto."""
    global _last_failure_warning
    now = _now()
    if _last_failure_warning is None or now - _last_failure_warning >= _WARNING_INTERVAL_SECONDS:
        _last_failure_warning = now
        logger.warning(
            "La búsqueda por palabras falló (%s: %s): la consulta usa el significado", type(exc).__name__, exc
        )


def reset_lexical_state() -> None:
    """Olvida el último aviso (para las pruebas)."""
    global _last_failure_warning
    _last_failure_warning = None
