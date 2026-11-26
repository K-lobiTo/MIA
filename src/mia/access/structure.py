"""Eliminación de programas y dominios (feature 023). Diseño en specs/023-eliminar-programas-dominios/research.md.

Solo se elimina lo vacío: un dominio sin documentos ni carpetas, un programa sin dominios, usuarios de la Consulta,
cuentas de administración ni artefactos con acceso a él. No hay cascada de contenido. Cada eliminación es una sola
transacción: bloquea la fila (en Postgres impide que entre algo nuevo mientras tanto), vuelve a comprobar, borra y confirma.

Los textos que salen de aquí los lee una persona sin conocimiento técnico."""

import logging
from dataclasses import dataclass, field

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mia.access.permissions import configured_domain_ids
from mia.access.scope import Principal, artifact_in_scope
from mia.storage.models import (
    Admin,
    AdminUnit,
    Artifact,
    ArtifactDomain,
    ArtifactUnit,
    Bot,
    ConsultaUser,
    DeletedDomain,
    Document,
    Domain,
    Folder,
    Unit,
)
from mia.storage.vector_store import VectorStore

logger = logging.getLogger(__name__)

# Nombres que se listan como máximo por cada impedimento o afectado (la cantidad siempre es el total).
MAX_NAMES = 10


@dataclass
class Item:
    """Algo que impide eliminar, o a quién afecta."""

    kind: str
    count: int
    names: list[str] = field(default_factory=list)
    hint: str = ""


class NotFound(Exception):
    pass


class Blocked(Exception):
    def __init__(self, name: str, blockers: list[Item]):
        super().__init__(name)
        self.name = name
        self.blockers = blockers


class Changed(Exception):
    """Algo se agregó o cambió mientras se eliminaba: no se hizo nada."""


class StoreUnavailable(Exception):
    """No se pudo revisar el almacén de búsqueda: no se hizo nada."""


HINTS = {
    "documents": "Elimina primero sus documentos (en el Inventario puedes usar Seleccionar para elegir varios).",
    "folders": "Borra primero sus carpetas, una por una, empezando por las que están dentro de otras.",
    "domains": "Elimina primero esos dominios.",
    "consulta_users": "Cámbialos de programa en Usuarios de la Consulta.",
    "admins": "Las cuentas de administración no se gestionan desde el panel: pide a soporte técnico que las quite de este programa.",
    "artifacts": (
        "Edita cada artefacto en Artefactos y quítale este programa. Si es su único acceso, dale otro o elimina el artefacto "
        "(si lo usa un bot de WhatsApp, primero asígnale otro artefacto al bot)."
    ),
}

# Singular y plural de cada tipo de impedimento, para la frase del rechazo.
NOUNS = {
    "documents": ("documento", "documentos"),
    "folders": ("carpeta", "carpetas"),
    "domains": ("dominio", "dominios"),
    "consulta_users": ("usuario de la Consulta", "usuarios de la Consulta"),
    "admins": ("cuenta de administración", "cuentas de administración"),
    "artifacts": ("artefacto con acceso", "artefactos con acceso"),
}


def _blocker(kind: str, count: int, names: list[str] | None = None) -> Item:
    return Item(kind, count, (names or [])[:MAX_NAMES], HINTS[kind])


def blocked_message(what: str, name: str, blockers: list[Item]) -> str:
    """El rechazo en una frase por impedimento: cuántos, cuáles y qué hacer."""
    parts = []
    for item in blockers:
        noun = NOUNS[item.kind][0 if item.count == 1 else 1]
        listed = ""
        if item.names:
            rest = item.count - len(item.names)
            listed = f" ({', '.join(item.names)}{f' y {rest} más' if rest > 0 else ''})"
        parts.append(f"Tiene {item.count} {noun}{listed}. {item.hint}")
    return f"No se puede eliminar todavía el {what} '{name}'. " + " ".join(parts)


# ---------------------------------------------------------------------------------------------------------
# Comprobaciones
# ---------------------------------------------------------------------------------------------------------


def domain_blockers(session: Session, domain_id: str) -> list[Item]:
    found = []
    for kind, model in (("documents", Document), ("folders", Folder)):
        count = session.scalar(select(func.count()).select_from(model).where(model.domain_id == domain_id)) or 0
        if count:
            found.append(_blocker(kind, count))
    return found


def unit_blockers(session: Session, unit_id: str) -> list[Item]:
    queries = {
        "domains": select(Domain.name).where(Domain.unit_id == unit_id).order_by(Domain.name),
        "consulta_users": select(ConsultaUser.username).where(ConsultaUser.unit_id == unit_id).order_by(ConsultaUser.username),
        "admins": select(Admin.email).join(AdminUnit, AdminUnit.admin_id == Admin.id).where(AdminUnit.unit_id == unit_id).order_by(Admin.email),
        "artifacts": (
            select(Artifact.name).join(ArtifactUnit, ArtifactUnit.artifact_id == Artifact.id)
            .where(ArtifactUnit.unit_id == unit_id).order_by(Artifact.name)
        ),
    }
    found = []
    for kind, query in queries.items():
        names = list(session.scalars(query))
        if names:
            found.append(_blocker(kind, len(names), names))
    return found


def domain_affects(session: Session, principal: Principal, domain_id: str) -> list[Item]:
    """A quién afecta eliminar el dominio. Los artefactos que la persona no administra se cuentan pero no se nombran."""
    artifacts = list(session.scalars(select(Artifact).order_by(Artifact.name)))
    granted_ids = set(session.scalars(select(ArtifactDomain.artifact_id).where(ArtifactDomain.domain_id == domain_id)))
    granted = [a for a in artifacts if a.id in granted_ids]
    emptied = [a for a in artifacts if not a.all_domains and configured_domain_ids(session, a) == {domain_id}]

    def item(kind: str, affected: list[Artifact], hint: str) -> Item:
        names = [a.name for a in affected if artifact_in_scope(session, principal, a)]
        return Item(kind, len(affected), names[:MAX_NAMES], hint)

    found = []
    if granted:
        found.append(item("artifacts", granted, "Artefactos que dejarán de tener acceso a este dominio."))
    if emptied:
        found.append(item("empty_artifacts", emptied, "Artefactos que se quedarán sin ningún dominio que consultar."))
    touched = {a.id for a in granted} | {a.id for a in emptied}
    bots = list(session.scalars(select(Bot.name).where(Bot.artifact_id.in_(touched), Bot.active.is_(True)).order_by(Bot.name))) if touched else []
    if bots:
        found.append(Item("bots", len(bots), bots[:MAX_NAMES], "Bots de WhatsApp que usan esos artefactos y responden a personas externas."))
    return found


# ---------------------------------------------------------------------------------------------------------
# Eliminación
# ---------------------------------------------------------------------------------------------------------


def _lock(session: Session, model, row_id: str):
    """La fila bloqueada y recién leída (quien llega segundo ya no la encuentra). SQLite ignora el bloqueo."""
    row = session.scalar(select(model).where(model.id == row_id).with_for_update().execution_options(populate_existing=True))
    if row is None:
        raise NotFound()
    return row


def _clean_store(session: Session, store: VectorStore, domain_id: str) -> None:
    """Con el dominio ya sin documentos no debería haber fragmentos suyos. Los de un documento que no existe se borran;
    los de un documento que vive en otro dominio se reetiquetan (nunca se borra contenido de un documento vivo)."""
    for document_id in store.document_ids_in_domain(domain_id):
        document = session.get(Document, document_id)
        if document is None:
            store.delete_document(document_id)
        else:
            store.set_domain(document_id, document.domain_id)


def delete_domain(session: Session, store: VectorStore, domain_id: str) -> str:
    """Elimina un dominio vacío y devuelve su nombre. Se confirma solo si todo salió bien."""
    try:
        domain = _lock(session, Domain, domain_id)
        name = domain.name
        blockers = domain_blockers(session, domain_id)
        if blockers:
            raise Blocked(name, blockers)
        unit = session.get(Unit, domain.unit_id) if domain.unit_id else None
        session.add(DeletedDomain(id=domain_id, label=f"{unit.name} / {name}" if unit else name))
        session.execute(delete(ArtifactDomain).where(ArtifactDomain.domain_id == domain_id))
        # Borrado directo, sin la relación del ORM: así un documento o carpeta que acabara de entrar hace fallar la clave
        # foránea en vez de quedar sin dominio.
        if not session.execute(delete(Domain).where(Domain.id == domain_id)).rowcount:
            raise NotFound()
        session.flush()
        try:
            _clean_store(session, store, domain_id)
        except Exception as exc:
            logger.warning("No se pudo revisar el almacén al eliminar un dominio (%s: %s)", type(exc).__name__, exc)
            raise StoreUnavailable() from exc
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise Changed() from exc
    except Exception:
        session.rollback()
        raise
    return name


def delete_unit(session: Session, unit_id: str) -> str:
    """Elimina un programa vacío y sin asociaciones, y devuelve su nombre."""
    try:
        name = _lock(session, Unit, unit_id).name
        blockers = unit_blockers(session, unit_id)
        if blockers:
            raise Blocked(name, blockers)
        if not session.execute(delete(Unit).where(Unit.id == unit_id)).rowcount:
            raise NotFound()
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise Changed() from exc
    except Exception:
        session.rollback()
        raise
    return name
