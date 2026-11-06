"""Barrido de secciones (feature 016): resumir lo que dice la misma sección de todos los documentos de un tipo.

La búsqueda por significado trae los fragmentos más parecidos a la pregunta, así que una pregunta como "resume los
contenidos de los cursos" recibe unos pocos documentos y el modelo concluye que de los demás solo conoce el nombre.
Cada programa de curso tiene su sección «Contenidos» (una fila de la tabla del programa: `4. Contenidos | ...`), de
unos 700 a 2000 caracteres. Con QUERY_SECTION_SWEEP=on, una pregunta que pide resumir o listar los contenidos de los
cursos en plural salta la búsqueda por similitud: se buscan en los dominios consultados los documentos que tienen esa
fila, se lee de cada uno solo esa sección y todas se entregan al modelo en una sola llamada.

La detección es por reglas de texto (sin modelo de lenguaje). Un fallo, o menos de dos documentos con la sección, nunca
rompe la consulta: sigue la búsqueda de siempre. Ver specs/016-barrido-secciones/.
"""

import logging
import re
from concurrent.futures import ThreadPoolExecutor

from mia.rag.completeness import switch_enabled
from mia.rag.context import Passage, join_consecutive
from mia.rag.lexical import normalize
from mia.storage.vector_store import VectorStore

logger = logging.getLogger(__name__)

# Fragmentos con la palabra «contenidos» que se revisan como máximo en los dominios (el documento del programa y las
# actas la repiten muchas veces; las filas de los programas de curso son una por documento).
SCAN_LIMIT = 3000
# Fragmentos que se leen desde el que trae el encabezado (unos 800 caracteres nuevos cada uno): sobra para una sección.
WINDOW = 8
WORKERS = 8

_COURSES = re.compile(r"\b(?:cursos|materias|asignaturas)\b")
_ASKS = re.compile(
    r"\b(?:resum\w*|sintetiz\w*|sintesis|contenid\w*|temari\w*|temas|que se (?:ve|vera|estudia|aprende|aprenden)"
    r"|que (?:aprend\w*|estudi\w*)|de que tratan)\b"
)
# Si la pregunta pide además otro dato de los cursos (créditos, requisitos...) el barrido de contenidos no la responde.
_OTHER = re.compile(
    r"\b(?:creditos?|horas?|requisitos?|correquisitos?|costos?|precios?|profesor\w*|docentes?|evalua\w*|notas?"
    r"|horarios?|cuando|cuanto\w*|cuantas?|matricul\w*|aprobar|reprobar)\b"
)

# La fila «4. Contenidos | ...» (el número es opcional: algunos programas no lo llevan) al comienzo de una línea.
_HEADING = re.compile(r"(?im)^[ \t]*(?:\d+[ \t]*\.?[ \t]*)?contenidos?[ \t]*\|")
# La fila siguiente de la tabla: un número y un título seguido de la celda (`5. Metodología de enseñanza | ...`).
_NEXT_ROW = re.compile(r"(?m)^[ \t]*\d+[ \t]*\.?[ \t]+[^\n|]{3,80}?[ \t]*\|")

SWEEP_INSTRUCTIONS = (
    "Los fragmentos son la sección «Contenidos» de los programas de curso, uno por documento y ya completos; el nombre "
    "del curso es el del documento (sin la extensión). Resume los contenidos de CADA curso, uno por uno, en el orden "
    "en que se te entregaron, con el nombre del curso y tres a cinco viñetas con sus temas principales. No omitas "
    "ningún documento y no digas que falta información de un curso cuyo fragmento se te entregó."
)


def section_sweep_enabled(value: str) -> bool:
    return switch_enabled(value, "QUERY_SECTION_SWEEP")


def wants_course_contents(question: str) -> bool:
    """Si la pregunta pide resumir o listar lo que se ve en los cursos en general (plural), sin otro dato de ellos."""
    plain = normalize(question)
    return bool(_COURSES.search(plain) and _ASKS.search(plain) and not _OTHER.search(plain))


def has_contents_heading(text: str) -> bool:
    return _HEADING.search(text) is not None


def section_from(text: str, max_chars: int) -> str | None:
    """La fila «Contenidos» del texto, desde su encabezado hasta la fila siguiente (o `max_chars`); nulo si no la tiene."""
    heading = _HEADING.search(text)
    if heading is None:
        return None
    rest = text[heading.start() :]
    following = _NEXT_ROW.search(rest, heading.end() - heading.start())
    if following is not None:
        rest = rest[: following.start()]
    return rest[:max_chars].strip()


def sweep_sections(
    vector_store: VectorStore, domains: list[str], max_documents: int, max_chars: int
) -> list[Passage]:
    """Un pasaje con la sección «Contenidos» de cada documento de los dominios que la tiene (los de menor identificador
    hasta `max_documents`). Vacío si no hay ninguno o si algo falla."""
    try:
        starts: dict[str, tuple[int, str]] = {}
        for hit in vector_store.scan_chunks(domains, "contenidos", SCAN_LIMIT):
            if not has_contents_heading(hit.text):
                continue
            known = starts.get(hit.document_id)
            if known is None or hit.chunk_index < known[0]:
                starts[hit.document_id] = (hit.chunk_index, hit.domain)

        def read(document_id: str) -> Passage | None:
            first, domain = starts[document_id]
            chunks = sorted(
                vector_store.get_chunks(document_id, list(range(first, first + WINDOW))), key=lambda c: c.chunk_index
            )
            if not chunks:
                return None
            text = chunks[0].text
            for chunk in chunks[1:]:
                text = join_consecutive(text, chunk.text)
            section = section_from(text, max_chars)
            if not section:
                return None
            return Passage(
                document_id=document_id,
                domain=domain,
                text=section,
                first_index=first,
                last_index=chunks[-1].chunk_index,
                score=1.0,
            )

        selected = sorted(starts)[:max_documents]
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            passages = [p for p in pool.map(read, selected) if p is not None]
        return passages
    except Exception:
        logger.warning("Falló el barrido de secciones: la consulta sigue con la búsqueda de siempre", exc_info=True)
        return []


def sweep_note(passages: list[Passage]) -> str:
    return f"Barrido de secciones: {len(passages)} documentos"
