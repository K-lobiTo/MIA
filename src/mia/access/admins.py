"""Lista de administradores del panel: quién puede entrar y con qué alcance. Es lo único que escribe
las tablas `admins` y `admin_units` (lo usa scripts/admin.py)."""

import uuid
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from mia.access.scope import Principal
from mia.storage.models import Admin, AdminUnit, Unit


@dataclass(frozen=True)
class AdminInfo:
    email: str
    is_global: bool
    units: list[str]
    active: bool


def normalize_email(text: str) -> str:
    email = text.strip().lower()
    if "@" not in email or email.startswith("@") or email.endswith("@") or " " in email:
        raise ValueError(f"'{text}' no parece un correo.")
    return email


def add_admin(session: Session, email: str, *, is_global: bool, unit_names: list[str]) -> Admin:
    """Agrega un administrador, o actualiza el alcance de uno existente y lo reactiva. El alcance es
    global o al menos una unidad (por nombre), nunca ninguno."""
    email = normalize_email(email)
    if is_global and unit_names:
        raise ValueError("El alcance es global o de programas, no ambos.")
    if not is_global and not unit_names:
        raise ValueError("Indica el alcance: global o al menos un programa.")
    units: list[Unit] = []
    for name in dict.fromkeys(unit_names):
        unit = session.scalar(select(Unit).where(Unit.name == name))
        if unit is None:
            known = ", ".join(sorted(u.name for u in session.scalars(select(Unit)))) or "ninguna"
            raise ValueError(f"No existe el programa '{name}'. Programas: {known}.")
        units.append(unit)

    admin = session.scalar(select(Admin).where(Admin.email == email))
    if admin is None:
        admin = Admin(id=str(uuid.uuid4()), email=email)
        session.add(admin)
        session.flush()
    admin.is_global = is_global
    admin.active = True
    session.execute(delete(AdminUnit).where(AdminUnit.admin_id == admin.id))
    session.add_all([AdminUnit(admin_id=admin.id, unit_id=unit.id) for unit in units])
    session.commit()
    return admin


def list_admins(session: Session) -> list[AdminInfo]:
    unit_names = {u.id: u.name for u in session.scalars(select(Unit))}
    result = []
    for admin in session.scalars(select(Admin).order_by(Admin.email)):
        ids = session.scalars(select(AdminUnit.unit_id).where(AdminUnit.admin_id == admin.id))
        result.append(
            AdminInfo(
                email=admin.email,
                is_global=admin.is_global,
                units=sorted(unit_names.get(i, i) for i in ids),
                active=admin.active,
            )
        )
    return result


def deactivate_admin(session: Session, email: str) -> None:
    """Desactiva sin borrar: conserva el registro de quién tuvo acceso."""
    admin = session.scalar(select(Admin).where(Admin.email == normalize_email(email)))
    if admin is None:
        raise ValueError(f"No hay ningún administrador con el correo '{email}'.")
    admin.active = False
    session.commit()


def find_active_admin(session: Session, email: str) -> Principal | None:
    """El Principal del correo si está en la lista y activo; None si no."""
    admin = session.scalar(select(Admin).where(Admin.email == email.strip().lower(), Admin.active.is_(True)))
    if admin is None:
        return None
    unit_ids = frozenset(session.scalars(select(AdminUnit.unit_id).where(AdminUnit.admin_id == admin.id)))
    return Principal(email=admin.email, is_global=admin.is_global, unit_ids=unit_ids, source="entra")


def has_active_global(session: Session) -> bool:
    return session.scalar(select(Admin.id).where(Admin.is_global.is_(True), Admin.active.is_(True)).limit(1)) is not None
