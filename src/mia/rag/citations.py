"""Citas del modelo y selección de las fuentes que se muestran con la respuesta.

Con la opción QUERY_CITED_SOURCES encendida, a cada pasaje que se le entrega al modelo se le pone un
número y se le pide cerrar la respuesta con una línea `FUENTES: 1, 3` con los que usó. Aquí se
interpreta esa línea (se quita del texto y se valida contra los pasajes entregados) y se decide qué
fuentes se listan; si el modelo no cita nada utilizable, se listan todas, como siempre (trazabilidad,
principio V de la constitución). Ver specs/006-fuentes-que-aportaron/contracts/citas-y-fuentes.md.
"""

import logging

logger = logging.getLogger(__name__)

_VALORES_ENCENDIDO = {"on", "true", "1", "yes"}
_VALORES_APAGADO = {"off", "false", "0", "no", ""}
# Valores inválidos ya avisados en este proceso: el aviso sale una sola vez por valor, no en cada consulta.
_INVALID_VALUES_WARNED: set[str] = set()


def cited_sources_enabled(value: str) -> bool:
    """Si QUERY_CITED_SOURCES está encendida. Un valor inválido se trata como apagado y avisa una vez."""
    normalizado = (value or "").strip().lower()
    if normalizado in _VALORES_ENCENDIDO:
        return True
    if normalizado not in _VALORES_APAGADO and normalizado not in _INVALID_VALUES_WARNED:
        _INVALID_VALUES_WARNED.add(normalizado)
        logger.warning(
            "QUERY_CITED_SOURCES tiene un valor inválido (%r): se trata como apagado. Usar on u off.", value
        )
    return False

import re
import unicodedata
from dataclasses import dataclass, field

# Párrafo que se agrega a las instrucciones del modo cuando la opción está encendida.
CITATION_INSTRUCTIONS = (
    "Después de tu respuesta, en una última línea aparte, escribe FUENTES: seguido de los números de "
    "los fragmentos que realmente usaste, separados por comas (por ejemplo: FUENTES: 1, 3). Cita solo "
    "los fragmentos de los que tomaste información; no cites todos los que recibiste. No uses estos "
    "números dentro del texto de la respuesta. Si respondes SIN_INFORMACION, no escribas esa línea."
)

# Lo que puede haber después de "FUENTES:" para que se reconozca como línea de citas: números, separadores,
# corchetes, la palabra "y" o una negación ("ninguna"). Cualquier otra cosa es una frase del modelo y no se toca.
_CONTENIDO_DE_CITAS = re.compile(r"^(?:[\s\d,;.\[\]()y]*|\s*(?:ninguna|ninguno|n/a)\s*\.?\s*)$", re.IGNORECASE)
_MARCAS_DE_FORMATO = re.compile(r"[*_#>`~\s]+")


@dataclass
class ParsedCitations:
    """Respuesta del modelo separada de su línea de citas."""

    text: str
    cited: list[int] = field(default_factory=list)
    invalid: list[int] = field(default_factory=list)
    line_found: bool = False


@dataclass
class SourceSelection:
    """Qué pasajes se listan como fuentes (posiciones desde 1) y si rigió la regla de seguridad."""

    indexes: list[int]
    safety_rule: bool = False


def _sin_tildes(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def parse_citations(text: str, total: int) -> ParsedCitations:
    """Separa la línea `FUENTES: ...` del final del texto y valida los números contra los `total` pasajes.

    Solo se mira la última línea no vacía. Si se reconoce, se quita del texto aunque no tenga números
    utilizables. `cited` contiene únicamente enteros entre 1 y `total`, sin repetir y en orden creciente.
    """
    lineas = text.rstrip().split("\n")
    if not lineas or not lineas[-1].strip():
        return ParsedCitations(text=text)
    ultima = lineas[-1]
    compacta = _MARCAS_DE_FORMATO.sub("", _sin_tildes(ultima)).lower()
    prefijo = next((p for p in ("fuentes:", "fuente:") if compacta.startswith(p)), None)
    if prefijo is None:
        return ParsedCitations(text=text)
    contenido = _sin_tildes(ultima).split(":", 1)[1].strip(" *_`~")
    if not _CONTENIDO_DE_CITAS.match(contenido):
        return ParsedCitations(text=text)
    limpio = "\n".join(lineas[:-1]).rstrip()
    if not limpio:
        # La respuesta era solo la línea: se deja como llegó para no devolver un texto vacío.
        return ParsedCitations(text=text)
    numeros = [int(n) for n in re.findall(r"\d+", contenido)]
    validos = sorted({n for n in numeros if 1 <= n <= total})
    invalidos = sorted({n for n in numeros if not 1 <= n <= total})
    return ParsedCitations(text=limpio, cited=validos, invalid=invalidos, line_found=True)


def select_sources(parsed: ParsedCitations, total: int) -> SourceSelection:
    """Pasajes que se listan como fuentes: los citados válidos, en el orden original de entrega.

    Regla de seguridad: si no hay ninguna cita válida (sin línea, sin números o todos fuera de rango) se
    listan todos los pasajes entregados, como siempre, y se avisa con `safety_rule`. Una respuesta con
    contenido nunca queda sin fuentes.
    """
    if parsed.cited:
        return SourceSelection(indexes=list(parsed.cited), safety_rule=False)
    return SourceSelection(indexes=list(range(1, total + 1)), safety_rule=True)


# Nota que queda en el registro de Uso (campo reject_reason, que el panel muestra junto al resultado) en
# las consultas respondidas donde rigió la regla de seguridad.
SAFETY_RULE_NOTE = "Fuentes: sin citas utilizables, se mostraron todas"
