"""Reglas de texto de los datos de contacto (feature 017, specs/017-datos-contacto-whatsapp/research.md R4).

Reconocen, sin modelo de lenguaje, qué es un mensaje que responde a la invitación a dejar nombre y correo: una negativa, un
"para qué", un correo, un nombre, una frase de borrado o de reapertura. Todo es determinista, ignora mayúsculas y tildes al
comparar frases de control y NUNCA lanza. Son conservadoras a propósito: un falso positivo guarda una pregunta como si fuera
un nombre (y se la traga), así que ante la duda un mensaje es una pregunta y sigue el flujo normal.

Nada de aquí se registra: ni el teléfono, ni el nombre, ni el correo, ni el texto de la persona.
"""

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

Kind = Literal["erase", "reopen", "decline", "why", "provided", "bad_email", "question"]

EXAMPLE_EMAIL = "ana@correo.com"

NAME_MAX = 80
EMAIL_MAX = 254
# Con más caracteres que esto una frase de control (borrado, reapertura) es una pregunta larga que casualmente las nombra.
_CONTROL_MAX_CHARS = 80
_WHY_MAX_CHARS = 60

_PARTICLES = {"de", "del", "la", "las", "los", "y", "van", "von"}
_GREETINGS = {"hola", "buenas", "buenos", "dias", "tardes", "noches", "hey", "saludos"}
_FILLER = _GREETINGS | {"gracias", "ok", "si", "listo", "claro", "vale", "bueno", "porfa", "favor", "por"}
# Palabras propias de las preguntas sobre los programas: una frase capitalizada que las use es una pregunta, no un nombre.
_DOMAIN_WORDS = {
    "programa", "programas", "maestria", "doctorado", "posgrado", "licenciatura", "requisito", "requisitos", "admision",
    "matricula", "inscripcion", "costo", "costos", "horario", "horarios", "beca", "becas", "curso", "cursos", "plan",
    "fecha", "fechas", "informacion",
}
_DECLINES = {
    "no", "omitir", "paso", "ahora no", "por ahora no", "prefiero no", "no quiero", "no deseo", "saltar", "cancelar",
    "no quiero dejarlos", "no quiero dejar mis datos", "prefiero no dejarlos",
}
_WHY_TRIGGERS = ("para que", "por que", "privacidad", "que hacen con", "quien ve")
_WHY_SUBJECTS = ("datos", "correo", "numero")

_EMAIL = re.compile(r"[\w.+%'-]+@[\w-]+(?:\.[\w-]+)+")
_ERASE = re.compile(
    r"\b(?:borr\w*|elimin\w*|quit\w*|suprim\w*)\b.*\b(?:mis datos(?: personales)?|mi informacion|mi correo|mi nombre|mi numero|mi telefono)\b"
)
_REOPEN = re.compile(
    r"\b(?:dej\w*|dar|actualiz\w*|cambi\w*|corregir|corrij\w*|modific\w*|registr\w*)\b(?:\s+\w+){0,2}\s+"
    r"(?:mis datos|mi correo|mi nombre|mi informacion)\b"
)
_INTRO_EXPLICIT = re.compile(r"\b(?:me\s+llamo|mi\s+nombre\s+es)\b", re.IGNORECASE)
_INTRO_SOY = re.compile(r"\bsoy\b", re.IGNORECASE)
_EMAIL_LABEL = re.compile(
    r"\bmi\s+(?:correo|email|e-mail|mail)(?:\s+electr[oó]nico)?(?:\s+es)?\b|\b(?:correo|email|e-mail|mail)\s*:",
    re.IGNORECASE,
)
_NAME_WORD = re.compile(r"[^\W\d_]+(?:['’.\-][^\W\d_]+)*\.?")


@dataclass(frozen=True)
class Reading:
    """Qué es un mensaje: `kind`, y el `name` y el `email` reconocidos cuando los hay (el correo en minúsculas)."""

    kind: Kind
    name: str | None = None
    email: str | None = None


def fold(text: str) -> str:
    """Minúsculas y sin tildes."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def _plain(text: str) -> str:
    """Sin tildes, en minúsculas, sin signos de puntuación y con espacios simples."""
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", fold(text))).strip()


def _is_decline(plain: str) -> bool:
    for suffix in (" gracias", " por ahora"):
        if plain.endswith(suffix):
            plain = plain[: -len(suffix)].strip()
    for suffix in (" gracias", " por ahora"):
        if plain.endswith(suffix):
            plain = plain[: -len(suffix)].strip()
    return plain in _DECLINES


def _is_why(plain: str) -> bool:
    return (
        len(plain) <= _WHY_MAX_CHARS
        and any(trigger in plain for trigger in _WHY_TRIGGERS)
        and any(re.search(rf"\b{subject}\b", plain) for subject in _WHY_SUBJECTS)
    )


def _capitalized(word: str) -> bool:
    return word[:1].isupper()


def _name_from(text: str, *, email_present: bool) -> str | None:
    """El nombre que hay en un texto (ya sin el correo), o None si no parece un nombre."""
    if any(mark in text for mark in "?¿!¡"):
        return None
    explicit = bool(_INTRO_EXPLICIT.search(text))
    soy = bool(_INTRO_SOY.search(text))
    rest = _INTRO_EXPLICIT.sub(" ", text)
    rest = _INTRO_SOY.sub(" ", rest)
    rest = _EMAIL_LABEL.sub(" ", rest)
    rest = re.sub(r"[,;:()\[\]<>]", " ", rest)
    words = [w.strip(",;:!-") for w in rest.split()]
    words = [w for w in words if re.search(r"\w", w)]
    # Saludos al comienzo, "gracias" al final y conjunciones sueltas en los extremos no son parte del nombre.
    while words and fold(words[0].strip(".")) in _GREETINGS | {"y", "e"}:
        words.pop(0)
    while words and fold(words[-1].strip(".")) in {"gracias", "y", "e"}:
        words.pop()
    if not words or not all(_NAME_WORD.fullmatch(w) for w in words):
        return None
    core = [w for w in words if fold(w) not in _PARTICLES]
    if not core or fold(" ".join(words)) in _FILLER or all(fold(w) in _FILLER for w in core):
        return None
    if words[0].lower() in _PARTICLES or words[-1].lower() in _PARTICLES:
        return None
    if explicit or (email_present and not soy):
        ok = len(core) <= 4
    elif soy:
        ok = len(core) <= 4 and all(_capitalized(w) for w in core)
    else:
        ok = (
            2 <= len(core) <= 4
            and all(_capitalized(w) for w in core)
            and not any(fold(w.strip(".")) in _DOMAIN_WORDS for w in core)
        )
    if not ok:
        return None
    name = " ".join(words)
    return name[:NAME_MAX].rstrip()


def read_message(text: str | None, status: str) -> Reading:
    """Clasifica un mensaje de texto. Las frases de control (borrado y reapertura) valen en cualquier estado del contacto; el
    resto solo con la invitación abierta (`invitada`). Todo lo demás es una `question`."""
    try:
        return _read(text or "", status)
    except Exception:  # noqa: BLE001 - las reglas nunca deben tumbar el flujo: ante un fallo, es una pregunta
        return Reading("question")


def _read(text: str, status: str) -> Reading:
    text = text.strip()
    plain = _plain(text)
    if not plain:
        return Reading("question")

    if len(plain) <= _CONTROL_MAX_CHARS:
        if _ERASE.search(plain):
            return Reading("erase")
        if _REOPEN.search(plain):
            return Reading("reopen")

    if status != "invitada":
        return Reading("question")

    if _is_decline(plain):
        return Reading("decline")
    if _is_why(plain):
        return Reading("why")

    match = _EMAIL.search(text)
    if match is not None:
        email = match.group(0).lower()
        if len(email) > EMAIL_MAX:
            return Reading("bad_email")
        remainder = text[: match.start()] + " " + text[match.end() :]
        return Reading("provided", name=_name_from(remainder, email_present=True), email=email)

    if "@" in text or re.search(r"\barroba\b", plain):
        remainder = " ".join(token for token in text.split() if "@" not in token and fold(token) != "arroba")
        if "@" in text:
            # Un correo mal escrito ("ana@") sigue siendo un intento de dar el correo: el resto puede ser el nombre.
            return Reading("bad_email", name=_name_from(remainder, email_present=True))
        # Con "arroba" lo que queda ("ana correo") no es un nombre: solo cuenta con un introductor.
        has_intro = bool(_INTRO_EXPLICIT.search(remainder) or _INTRO_SOY.search(remainder))
        return Reading("bad_email", name=_name_from(remainder, email_present=False) if has_intro else None)

    name = _name_from(text, email_present=False)
    if name is not None:
        return Reading("provided", name=name)
    return Reading("question")


def mask_email(email: str) -> str:
    """El correo sin repetirlo completo en el chat: la primera letra y el dominio (`a**@correo.com`)."""
    local, _, domain = email.partition("@")
    return f"{local[:1]}**@{domain}"


def saved_phrase(name: str | None, email: str | None) -> str:
    """Lo que se guardó, para confirmarlo: incluye el nombre (así la persona detecta un error) y el correo enmascarado."""
    parts = []
    if name:
        parts.append(f"tu nombre ({name})")
    if email:
        parts.append(f"tu correo ({mask_email(email)})")
    return " y ".join(parts)


def render_thanks(template: str, name: str | None, email: str | None) -> str:
    return template.replace("{saved}", saved_phrase(name, email))


def render_retry(template: str) -> str:
    return template.replace("{example}", EXAMPLE_EMAIL)
