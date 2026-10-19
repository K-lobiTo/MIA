from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Nombres estables para índices y restricciones: las migraciones de Alembic (sobre todo el modo
# batch de SQLite) necesitan poder referirse a ellos.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def _now() -> datetime:
    """Hora actual en UTC, sin zona (así se guardan y se comparan todas las fechas)."""
    return datetime.now(UTC).replace(tzinfo=None)


class Unit(Base):
    """Programa: agrupa dominios. Hoy son dos: la Unidad de Postgrados de Computación y el Área académica de
    Analítica de Negocios (la clase y la tabla conservan el nombre técnico `Unit`/`units`)."""

    __tablename__ = "units"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    description: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    domains: Mapped[list["Domain"]] = relationship(back_populates="unit")


class Domain(Base):
    __tablename__ = "domains"
    # El nombre es único dentro de su unidad: las dos unidades tienen un dominio "Currículum".
    __table_args__ = (UniqueConstraint("unit_id", "name"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    # Nullable en la base: los dominios anteriores a la reorganización no tienen unidad. La API la
    # exige al crear un dominio.
    unit_id: Mapped[str | None] = mapped_column(ForeignKey("units.id"), nullable=True)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    unit: Mapped[Unit | None] = relationship(back_populates="domains")
    documents: Mapped[list["Document"]] = relationship(back_populates="domain")
    folders: Mapped[list["Folder"]] = relationship(back_populates="domain")


class Folder(Base):
    """Carpeta dentro de un dominio, anidable. Solo organiza: la consulta es por dominio."""

    __tablename__ = "folders"
    # En SQL un parent_id nulo no participa de una restricción única, así que en la raíz del
    # dominio la unicidad del nombre la verifica la API.
    __table_args__ = (UniqueConstraint("domain_id", "parent_id", "name"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    domain_id: Mapped[str] = mapped_column(ForeignKey("domains.id"))
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("folders.id"), nullable=True)
    name: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    domain: Mapped[Domain] = relationship(back_populates="folders")
    documents: Mapped[list["Document"]] = relationship(back_populates="folder")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    domain_id: Mapped[str] = mapped_column(ForeignKey("domains.id"))
    folder_id: Mapped[str | None] = mapped_column(ForeignKey("folders.id"), nullable=True)
    filename: Mapped[str] = mapped_column(String)
    source_type: Mapped[str] = mapped_column(String)
    file_hash: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String, default="pending")
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    domain: Mapped[Domain] = relationship(back_populates="documents")
    folder: Mapped[Folder | None] = relationship(back_populates="documents")


class Artifact(Base):
    """Aplicación que consulta a MIA (cada instancia de la Consulta administrativa, un chatbot)."""

    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    description: Mapped[str] = mapped_column(String, default="")
    # Solo se guarda el SHA-256 de la clave: no se puede recuperar, solo verificar.
    key_hash: Mapped[str] = mapped_column(String, unique=True, index=True)
    key_prefix: Mapped[str] = mapped_column(String)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Verdadero: todos los dominios, incluidas unidades futuras.
    all_domains: Mapped[bool] = mapped_column(Boolean, default=False)
    # Lista separada por comas de "literal" y "razonamiento"; al menos uno.
    modes: Mapped[str] = mapped_column(String, default="literal")
    daily_cap_usd: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("0.50"))
    reasoning_daily_cap_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class ArtifactUnit(Base):
    """Acceso de un artefacto a una unidad completa, incluidos sus dominios futuros."""

    __tablename__ = "artifact_units"

    artifact_id: Mapped[str] = mapped_column(ForeignKey("artifacts.id"), primary_key=True)
    unit_id: Mapped[str] = mapped_column(ForeignKey("units.id"), primary_key=True)


class ArtifactDomain(Base):
    """Acceso de un artefacto a un dominio puntual."""

    __tablename__ = "artifact_domains"

    artifact_id: Mapped[str] = mapped_column(ForeignKey("artifacts.id"), primary_key=True)
    domain_id: Mapped[str] = mapped_column(ForeignKey("domains.id"), primary_key=True)


class Admin(Base):
    """Persona autorizada a usar el panel con su cuenta del TEC. El alcance es global o un conjunto de
    unidades (`AdminUnit`). Solo `mia.access.admins` escribe esta tabla."""

    __tablename__ = "admins"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    # Siempre en minúsculas y sin espacios.
    email: Mapped[str] = mapped_column(String, unique=True)
    is_global: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class AdminUnit(Base):
    """Unidad sobre la que un administrador de alcance de unidad puede ver y operar."""

    __tablename__ = "admin_units"

    admin_id: Mapped[str] = mapped_column(ForeignKey("admins.id"), primary_key=True)
    unit_id: Mapped[str] = mapped_column(ForeignKey("units.id"), primary_key=True)


class SiglaEquivalence(Base):
    """Equivalencia entre una sigla y una forma desarrollada (feature 010): la pregunta con una forma también busca
    la otra. Es global (vale para todos los dominios) y la edita el operador desde el panel. `sigla` y `form` están
    normalizadas (minúsculas, sin tildes, espacios simples) y sirven para comparar y buscar; `*_display` es lo que
    escribió la persona."""

    __tablename__ = "sigla_equivalences"
    __table_args__ = (UniqueConstraint("sigla", "form"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    sigla: Mapped[str] = mapped_column(String)
    form: Mapped[str] = mapped_column(String)
    sigla_display: Mapped[str] = mapped_column(String)
    form_display: Mapped[str] = mapped_column(String)
    created_by: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_by: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class QueryLog(Base):
    """Registro de cada consulta: base de los topes, del módulo Uso y de la evaluación."""

    __tablename__ = "queries"
    __table_args__ = (Index("ix_queries_artifact_id_created_at", "artifact_id", "created_at"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    # UTC
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)
    artifact_id: Mapped[str | None] = mapped_column(ForeignKey("artifacts.id"), nullable=True)
    question: Mapped[str] = mapped_column(Text, default="")
    domain_ids: Mapped[str] = mapped_column(Text, default="[]")  # JSON
    mode: Mapped[str] = mapped_column(String, default="literal")
    model: Mapped[str | None] = mapped_column(String, nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reasoning_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal(0))
    cost_estimated: Mapped[bool] = mapped_column(Boolean, default=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # answered, no_info, error, rejected_cap, rejected_permission
    outcome: Mapped[str] = mapped_column(String, default="answered")
    reject_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    sources: Mapped[str] = mapped_column(Text, default="[]")  # JSON: [{domain, document}]
    rating: Mapped[str | None] = mapped_column(String, nullable=True)  # util, no_util
    rating_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
