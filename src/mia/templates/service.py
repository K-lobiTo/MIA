"""Servicio de plantillas de respuesta (feature 020): validaciones, visibilidad, búsqueda y lectura de archivos.

La visibilidad la calcula siempre la API (nunca el cliente): para un artefacto A y, si hay sesión, una persona U, son visibles
las plantillas del artefacto A y las personales de U que valen para todos los artefactos (`artifact_id` nulo) o solo para A. El
contenido de una plantilla nunca se escribe en los registros ni en los mensajes de error."""

import re
import tempfile
import unicodedata
from pathlib import Path

from fastapi import HTTPException, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from mia.config import settings
from mia.ingestion.loaders.base import get_loader
from mia.storage.models import Artifact, ConsultaUser, ResponseTemplate

NAME_MAX_CHARS = 80
NOT_AVAILABLE = "La plantilla ya no está disponible."
FILE_TYPE_ERROR = "Solo se aceptan archivos .docx o .txt."
FILE_UNREADABLE = "No se pudo leer el archivo: está dañado o protegido con contraseña."
FILE_EMPTY = "El archivo no tiene texto."
EXTENSIONS = (".docx", ".txt")


def normalize_name(name: str) -> str:
    """La clave de unicidad del nombre: sin tildes, en minúsculas, sin espacios repetidos."""
    decomposed = unicodedata.normalize("NFKD", name)
    plain = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", plain).strip().lower()


def validate_name(name: str) -> str:
    """El nombre recortado, o 422 si está vacío, es demasiado largo o tiene saltos de línea."""
    clean = (name or "").strip()
    if not clean:
        raise HTTPException(status_code=422, detail="El nombre no puede estar vacío.")
    if "\n" in clean or "\r" in clean:
        raise HTTPException(status_code=422, detail="El nombre no puede tener saltos de línea.")
    if len(clean) > NAME_MAX_CHARS:
        raise HTTPException(status_code=422, detail=f"El nombre no puede superar {NAME_MAX_CHARS} caracteres.")
    return clean


def validate_content(content: str) -> str:
    """El contenido sin espacios en los extremos, o 422 si está vacío o supera `template_max_chars`."""
    clean = (content or "").strip()
    if not clean:
        raise HTTPException(status_code=422, detail="El contenido no puede estar vacío.")
    if len(clean) > settings.template_max_chars:
        raise HTTPException(
            status_code=422, detail=f"El contenido no puede superar {settings.template_max_chars} caracteres."
        )
    return clean


def artifact_owner_key(artifact_id: str) -> str:
    return f"a:{artifact_id}"


def user_owner_key(user_id: str) -> str:
    return f"u:{user_id}"


def visible_templates(
    session: Session, artifact: Artifact, user: ConsultaUser | None
) -> tuple[list[ResponseTemplate], list[ResponseTemplate]]:
    """(las del artefacto, las personales de la persona visibles en este artefacto). Sin sesión, las segundas van vacías."""
    of_artifact = list(
        session.scalars(
            select(ResponseTemplate)
            .where(ResponseTemplate.scope == "artifact", ResponseTemplate.artifact_id == artifact.id)
            .order_by(ResponseTemplate.name_key)
        )
    )
    if user is None:
        return of_artifact, []
    mine = list(
        session.scalars(
            select(ResponseTemplate)
            .where(
                ResponseTemplate.scope == "personal",
                ResponseTemplate.user_id == user.id,
                or_(ResponseTemplate.artifact_id.is_(None), ResponseTemplate.artifact_id == artifact.id),
            )
            .order_by(ResponseTemplate.name_key)
        )
    )
    return of_artifact, mine


def resolve_template(
    session: Session, artifact: Artifact, user: ConsultaUser | None, template_id: str
) -> ResponseTemplate:
    """La plantilla si es visible para el artefacto y la persona; si no existe o no es visible, 404 con el mismo mensaje (así
    no se distingue una eliminada de una ajena)."""
    of_artifact, mine = visible_templates(session, artifact, user)
    for template in [*of_artifact, *mine]:
        if template.id == template_id:
            return template
    raise HTTPException(status_code=404, detail=NOT_AVAILABLE)


def count_for_artifact(session: Session, artifact_id: str) -> int:
    return session.scalar(
        select(func.count()).select_from(ResponseTemplate).where(
            ResponseTemplate.scope == "artifact", ResponseTemplate.artifact_id == artifact_id
        )
    ) or 0


def count_for_user(session: Session, user_id: str) -> int:
    return session.scalar(
        select(func.count()).select_from(ResponseTemplate).where(
            ResponseTemplate.scope == "personal", ResponseTemplate.user_id == user_id
        )
    ) or 0


def name_taken(session: Session, owner_key: str, name_key: str, exclude_id: str | None = None) -> bool:
    """Si ya hay otra plantilla con ese nombre dentro del mismo alcance (el artefacto, o las personales de una persona)."""
    query = select(ResponseTemplate.id).where(
        ResponseTemplate.owner_key == owner_key, ResponseTemplate.name_key == name_key
    )
    if exclude_id is not None:
        query = query.where(ResponseTemplate.id != exclude_id)
    return session.scalar(query) is not None


def prepare(name: str, content: str) -> tuple[str, str, str]:
    """(nombre recortado, clave del nombre, contenido recortado) ya validados; 422 con el límite si algo no cumple."""
    clean_name = validate_name(name)
    return clean_name, normalize_name(clean_name), validate_content(content)


def ensure_unique(session: Session, owner_key: str, name_key: str, message: str, exclude_id: str | None = None) -> None:
    """409 con `message` si ya hay otra plantilla con ese nombre dentro del mismo alcance."""
    if name_taken(session, owner_key, name_key, exclude_id):
        raise HTTPException(status_code=409, detail=message)


def ensure_room(current: int, limit: int, message: str) -> None:
    """422 con `message` si ya se llegó al máximo de plantillas."""
    if current >= limit:
        raise HTTPException(status_code=422, detail=message)


def iso(value) -> str:
    return value.isoformat() + "Z"


def changed_since(template: ResponseTemplate, expected_updated_at: str | None) -> JSONResponse | None:
    """Con `expected_updated_at` distinto de la versión actual (otra persona la editó), la respuesta 409 con la versión
    actual; si coincide, o no se envió, None (gana la última edición)."""
    if expected_updated_at is None or expected_updated_at == iso(template.updated_at):
        return None
    return JSONResponse(
        status_code=409,
        content={
            "detail": "La plantilla cambió desde que la abriste. Revisa la versión actual antes de guardar.",
            "code": "template_changed",
            "current": {
                "id": template.id, "name": template.name, "content": template.content, "updated_at": iso(template.updated_at)
            },
        },
    )


def extract_text(upload: UploadFile, max_chars: int, max_mb: int) -> str:
    """El texto de un `.docx` o `.txt` con los cargadores de la ingesta, para revisarlo antes de guardarlo como plantilla.
    El archivo se guarda solo en un directorio temporal y se borra siempre. Cualquier falla de lectura devuelve el mismo
    mensaje fijo, sin detalles de la excepción. Nunca recorta: un texto mayor que `max_chars` se rechaza."""
    extension = Path(upload.filename or "").suffix.lower()
    if extension not in EXTENSIONS:
        raise HTTPException(status_code=422, detail=FILE_TYPE_ERROR)
    limit = max_mb * 1024 * 1024
    content = upload.file.read(limit + 1)
    if len(content) > limit:
        raise HTTPException(status_code=413, detail=f"El archivo supera el tamaño máximo de {max_mb} MB.")
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / f"plantilla{extension}"
        path.write_bytes(content)
        try:
            text = get_loader(extension[1:]).load(path)
        except Exception:  # noqa: BLE001 - cualquier falla del cargador es "dañado o protegido", sin detalles
            raise HTTPException(status_code=422, detail=FILE_UNREADABLE) from None
    text = re.sub(r"\n{3,}", "\n\n", text.replace("\r\n", "\n").replace("﻿", "")).strip()
    if not text:
        raise HTTPException(status_code=422, detail=FILE_EMPTY)
    if len(text) > max_chars:
        raise HTTPException(
            status_code=422, detail=f"El texto del archivo supera el máximo de {max_chars} caracteres."
        )
    return text
