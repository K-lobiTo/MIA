"""Administración de los contactos de WhatsApp (feature 017): GET /contacts (JSON y CSV), DELETE /contacts/{id} y
DELETE /contacts (por filtro, con el conteo confirmado), que usa el módulo Contactos de WhatsApp del panel.

Todo con alcance global (los contactos no pertenecen a un programa). Cada descarga y cada borrado deja una línea en el registro
de administración con el conteo y los filtros, NUNCA con teléfonos, nombres ni correos. Contrato en
specs/017-datos-contacto-whatsapp/contracts/contactos-admin-api.md.
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from mia.access import audit
from mia.access.guards import ensure_global
from mia.access.scope import Principal
from mia.api.security import require_admin
from mia.contacts import csv_export
from mia.contacts import store as contacts_store
from mia.contacts.store import ContactFilters
from mia.storage.db import get_session
from mia.storage.models import Bot, WhatsAppContact, _now

router = APIRouter(tags=["contacts"])

# Tope de seguridad de la descarga: con más filas se pide filtrar.
MAX_CSV_ROWS = 50_000

Status = Literal["pendiente", "invitada", "entrego", "declino"]


def contact_filters(
    bot_id: str | None = None,
    status: Annotated[list[Status] | None, Query()] = None,
    has_email: bool | None = None,
) -> ContactFilters:
    return ContactFilters(bot_id=bot_id or None, statuses=list(status or []), has_email=has_email)


def _describe(filters: ContactFilters) -> str:
    """Los filtros para la línea de auditoría: ids de bot, estados y si tienen correo; nada de personas."""
    correo = "-" if filters.has_email is None else ("si" if filters.has_email else "no")
    return f"filtros=bot:{filters.bot_id or '-'},estado:{'|'.join(filters.statuses) or '-'},correo:{correo}"


def _iso(value) -> str:
    return value.isoformat() + "Z"


def _item(contact: WhatsAppContact, bots: dict[str, str]) -> dict:
    return {
        "id": contact.id,
        "phone": contact.phone,
        "bot": {"id": contact.bot_id, "name": bots.get(contact.bot_id, "")},
        "name": contact.name,
        "email": contact.email,
        "status": contact.status,
        "created_at": _iso(contact.created_at),
        "last_seen_at": _iso(contact.last_seen_at),
        "updated_at": _iso(contact.updated_at),
    }


def _bot_names(session: Session) -> dict[str, str]:
    return {b.id: b.name for b in session.scalars(select(Bot))}


@router.get("/contacts")
def list_contacts(
    filters: ContactFilters = Depends(contact_filters),
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
    format: Literal["json", "csv"] = "json",
    principal: Principal = Depends(require_admin),
    session: Session = Depends(get_session),
):
    ensure_global(principal, "contact.export" if format == "csv" else "contact.list")
    bots = _bot_names(session)
    if format == "csv":
        total = contacts_store.count(session, filters)
        if total > MAX_CSV_ROWS:
            raise HTTPException(
                status_code=422, detail=f"Hay demasiados contactos para una descarga ({total}): filtra por bot o por estado."
            )
        rows = contacts_store.all_contacts(session, filters, MAX_CSV_ROWS)
        audit.log_write(principal, "contact.export", detail=f"filas={len(rows)}; {_describe(filters)}")
        filename = f"mia-contactos-{_now().date().isoformat()}.csv"
        return Response(
            content=csv_export.to_csv(rows, bots),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    items, total = contacts_store.list_contacts(session, filters, page, page_size)
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_item(c, bots) for c in items],
        "summary": contacts_store.summary(session, filters),
    }


@router.delete("/contacts/{contact_id}", status_code=204)
def delete_contact(
    contact_id: str, principal: Principal = Depends(require_admin), session: Session = Depends(get_session)
) -> Response:
    ensure_global(principal, "contact.delete", detail=contact_id)
    if not contacts_store.delete_contact(session, contact_id):
        raise HTTPException(status_code=404, detail="Contacto no encontrado.")
    audit.log_write(principal, "contact.delete", target=contact_id)
    return Response(status_code=204)


@router.delete("/contacts")
def delete_filtered_contacts(
    expected: Annotated[int, Query(ge=0)],
    filters: ContactFilters = Depends(contact_filters),
    principal: Principal = Depends(require_admin),
    session: Session = Depends(get_session),
):
    """Borra todos los contactos del filtro, solo si el conteo coincide con el que la persona vio y confirmó."""
    ensure_global(principal, "contact.delete_filtered")
    current = contacts_store.count(session, filters)
    if current != expected:
        return JSONResponse(
            status_code=409,
            content={"detail": "El número de contactos cambió: revisa la lista y vuelve a intentar.", "count": current},
        )
    deleted = contacts_store.delete_filtered(session, filters)
    audit.log_write(principal, "contact.delete_filtered", detail=f"borrados={deleted}; {_describe(filters)}")
    return {"deleted": deleted}
