"""Comprobaciones de alcance que cortan la petición con un error de acceso y dejan constancia del
rechazo en el registro de administración."""

from sqlalchemy.orm import Session

from mia.access import audit
from mia.access.errors import global_only, out_of_scope
from mia.access.scope import Principal, can_grant_access, domain_in_scope, unit_in_scope
from mia.storage.models import Domain


def ensure_global(principal: Principal, action: str, detail: str = "") -> None:
    if not principal.is_global:
        audit.log_write(principal, action, detail=detail, result="rechazado")
        raise global_only()


def ensure_unit(principal: Principal, unit_id: str | None, action: str, target: str = "") -> None:
    if not unit_in_scope(principal, unit_id):
        audit.log_write(principal, action, target, result="rechazado")
        raise out_of_scope()


def ensure_domain(principal: Principal, domain: Domain, action: str) -> None:
    if not domain_in_scope(principal, domain):
        audit.log_write(principal, action, domain.id, result="rechazado")
        raise out_of_scope()


def ensure_can_grant(
    session: Session,
    principal: Principal,
    all_domains: bool,
    unit_ids: list[str],
    domain_ids: list[str],
    action: str,
    target: str = "",
) -> None:
    """El acceso que se da a un artefacto debe caer dentro del alcance; "todos los dominios" es solo global."""
    if not can_grant_access(session, principal, all_domains, unit_ids, domain_ids):
        audit.log_write(principal, action, target, result="rechazado")
        raise out_of_scope("Un artefacto solo puede dar acceso a dominios de tus unidades.")
