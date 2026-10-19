"""Lista de equivalencias de siglas de la búsqueda híbrida (feature 010), que el operador mantiene desde el panel.

Lectura para cualquier persona que administra; escritura solo del alcance global (la lista vale para todos los
dominios). Cada cambio invalida la caché de la API y deja una línea en el registro de administración. Ver
specs/010-busqueda-hibrida/contracts/equivalencias-api.md."""

import re
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from mia.access import audit
from mia.access.guards import ensure_global
from mia.access.scope import Principal
from mia.api.security import require_admin
from mia.rag.equivalences import invalidate_equivalences
from mia.rag.lexical import normalize, words_of
from mia.storage.db import get_session
from mia.storage.models import SiglaEquivalence

router = APIRouter(tags=["equivalences"])

SIGLA_MIN, SIGLA_MAX = 3, 20
FORM_MIN, FORM_MAX = 3, 120


class EquivalenceInput(BaseModel):
    sigla: str
    form: str


class EquivalenceUpdate(BaseModel):
    sigla: str | None = None
    form: str | None = None


class EquivalenceOut(BaseModel):
    id: str
    sigla: str
    form: str
    created_by: str
    created_at: str
    updated_by: str | None = None
    updated_at: str | None = None


class EquivalencesOut(BaseModel):
    equivalences: list[EquivalenceOut]


def _invalid(field: str, reason: str) -> HTTPException:
    return HTTPException(status_code=422, detail=f"{field}: {reason}")


def clean_sigla(value: str) -> tuple[str, str]:
    """(texto como lo escribió la persona, sigla normalizada). Letras y dígitos; se aceptan puntos y espacios."""
    shown = (value or "").strip()
    if not shown:
        raise _invalid("sigla", "no puede estar vacía.")
    if re.search(r"[^\w .]|_", shown):
        raise _invalid("sigla", "solo puede llevar letras y dígitos (se aceptan puntos y espacios).")
    normalized = re.sub(r"[^a-z0-9]", "", normalize(shown))
    if not SIGLA_MIN <= len(normalized) <= SIGLA_MAX:
        raise _invalid("sigla", f"debe tener de {SIGLA_MIN} a {SIGLA_MAX} caracteres.")
    return shown, normalized


def clean_form(value: str) -> tuple[str, str]:
    """(texto como lo escribió la persona, forma normalizada: palabras en minúsculas, sin tildes, separadas por un espacio)."""
    shown = (value or "").strip()
    if not shown:
        raise _invalid("forma desarrollada", "no puede estar vacía.")
    normalized = " ".join(words_of(shown))
    if not FORM_MIN <= len(normalized) <= FORM_MAX:
        raise _invalid("forma desarrollada", f"debe tener de {FORM_MIN} a {FORM_MAX} caracteres.")
    if not any(len(word) >= 3 for word in normalized.split()):
        raise _invalid("forma desarrollada", "debe llevar al menos una palabra de 3 letras o más.")
    return shown, normalized


def _check_pair(sigla: str, form: str) -> None:
    if form == sigla:
        raise _invalid("forma desarrollada", "no puede ser igual a la sigla.")


def _out(row: SiglaEquivalence) -> EquivalenceOut:
    def iso(value):
        return value.isoformat() if value is not None else None

    return EquivalenceOut(
        id=row.id, sigla=row.sigla_display, form=row.form_display, created_by=row.created_by,
        created_at=iso(row.created_at), updated_by=row.updated_by, updated_at=iso(row.updated_at),
    )


def _existing(session: Session, sigla: str, form: str, ignore_id: str | None = None) -> SiglaEquivalence | None:
    row = session.scalar(
        select(SiglaEquivalence).where(SiglaEquivalence.sigla == sigla, SiglaEquivalence.form == form)
    )
    return row if row is not None and row.id != ignore_id else None


def _conflict(row: SiglaEquivalence) -> HTTPException:
    return HTTPException(
        status_code=409, detail=f"Ya existe la equivalencia «{row.sigla_display}» = «{row.form_display}»."
    )


@router.get("/equivalences", response_model=EquivalencesOut)
def list_equivalences(
    principal: Principal = Depends(require_admin), session: Session = Depends(get_session)
) -> EquivalencesOut:
    rows = session.scalars(select(SiglaEquivalence).order_by(SiglaEquivalence.sigla, SiglaEquivalence.form))
    return EquivalencesOut(equivalences=[_out(row) for row in rows])


@router.post("/equivalences", response_model=EquivalenceOut, status_code=201)
def create_equivalence(
    payload: EquivalenceInput,
    principal: Principal = Depends(require_admin),
    session: Session = Depends(get_session),
) -> EquivalenceOut:
    ensure_global(principal, "equivalence.create", payload.sigla)
    sigla_shown, sigla = clean_sigla(payload.sigla)
    form_shown, form = clean_form(payload.form)
    _check_pair(sigla, form)
    duplicate = _existing(session, sigla, form)
    if duplicate is not None:
        raise _conflict(duplicate)
    row = SiglaEquivalence(
        id=str(uuid.uuid4()), sigla=sigla, form=form, sigla_display=sigla_shown, form_display=form_shown,
        created_by=principal.label,
    )
    session.add(row)
    session.commit()
    invalidate_equivalences()
    audit.log_write(principal, "equivalence.create", row.id, f"{sigla_shown} = {form_shown}")
    return _out(row)


@router.patch("/equivalences/{equivalence_id}", response_model=EquivalenceOut)
def update_equivalence(
    equivalence_id: str,
    payload: EquivalenceUpdate,
    principal: Principal = Depends(require_admin),
    session: Session = Depends(get_session),
) -> EquivalenceOut:
    ensure_global(principal, "equivalence.update", equivalence_id)
    row = session.get(SiglaEquivalence, equivalence_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Equivalencia no encontrada.")
    if payload.sigla is None and payload.form is None:
        raise _invalid("equivalencia", "indica la sigla, la forma desarrollada o las dos.")
    sigla_shown, sigla = clean_sigla(payload.sigla) if payload.sigla is not None else (row.sigla_display, row.sigla)
    form_shown, form = clean_form(payload.form) if payload.form is not None else (row.form_display, row.form)
    _check_pair(sigla, form)
    duplicate = _existing(session, sigla, form, ignore_id=row.id)
    if duplicate is not None:
        raise _conflict(duplicate)
    before = f"{row.sigla_display} = {row.form_display}"
    row.sigla, row.form, row.sigla_display, row.form_display = sigla, form, sigla_shown, form_shown
    row.updated_by = principal.label
    row.updated_at = datetime.now(UTC).replace(tzinfo=None)
    session.commit()
    invalidate_equivalences()
    audit.log_write(principal, "equivalence.update", row.id, f"{before} -> {sigla_shown} = {form_shown}")
    return _out(row)


@router.delete("/equivalences/{equivalence_id}", status_code=204)
def delete_equivalence(
    equivalence_id: str,
    principal: Principal = Depends(require_admin),
    session: Session = Depends(get_session),
) -> Response:
    ensure_global(principal, "equivalence.delete", equivalence_id)
    row = session.get(SiglaEquivalence, equivalence_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Equivalencia no encontrada.")
    detail = f"{row.sigla_display} = {row.form_display}"
    session.delete(row)
    session.commit()
    invalidate_equivalences()
    audit.log_write(principal, "equivalence.delete", equivalence_id, detail)
    return Response(status_code=204)
