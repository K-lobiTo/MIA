"""Registro de consultas: listado paginado, detalle y exportación CSV."""

import csv
import io
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from mia.storage.models import Artifact, Domain, QueryLog, Unit

CSV_COLUMNS = [
    "id", "created_at", "artifact", "mode", "model", "prompt_tokens", "completion_tokens", "reasoning_tokens",
    "cost_usd", "cost_estimated", "latency_ms", "outcome", "reject_reason", "rating",
]
# Una celda que empieza con estos caracteres se interpreta como fórmula al abrir el CSV en una hoja de cálculo.
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _iso(row: QueryLog) -> str:
    return row.created_at.isoformat() + "Z"


def artifact_names(session: Session) -> dict[str, str]:
    return {a.id: a.name for a in session.scalars(select(Artifact))}


def list_item(row: QueryLog, names: dict[str, str]) -> dict:
    tokens = (row.prompt_tokens or 0) + (row.completion_tokens or 0)
    return {
        "id": row.id,
        "created_at": _iso(row),
        "artifact": names.get(row.artifact_id or ""),
        "mode": row.mode,
        "model": row.model,
        "tokens": tokens if row.prompt_tokens is not None or row.completion_tokens is not None else None,
        "cost_usd": float(row.cost_usd or 0),
        "cost_estimated": bool(row.cost_estimated),
        "latency_ms": row.latency_ms,
        "outcome": row.outcome,
        "reject_reason": row.reject_reason,
        "rating": row.rating,
    }


def detail(session: Session, row: QueryLog) -> dict:
    """Todo lo del listado, más la pregunta, los dominios consultados (con su unidad), los documentos citados y el comentario."""
    domain_ids = json.loads(row.domain_ids or "[]")
    units = {u.id: u.name for u in session.scalars(select(Unit))}
    domains = {d.id: d for d in session.scalars(select(Domain).where(Domain.id.in_(domain_ids)))} if domain_ids else {}
    labels = []
    for domain_id in domain_ids:
        domain = domains.get(domain_id)
        if domain is None:
            labels.append(f"({domain_id}, ya no existe)")
        else:
            unit = units.get(domain.unit_id or "")
            labels.append(f"{unit} / {domain.name}" if unit else domain.name)
    return {
        **list_item(row, artifact_names(session)),
        "question": row.question,
        "domains": labels,
        "sources": json.loads(row.sources or "[]"),
        "rating_comment": row.rating_comment,
    }


def _safe(value) -> str:
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(FORMULA_PREFIXES) else text


def to_csv(rows: list[QueryLog], names: dict[str, str], include_questions: bool) -> str:
    """CSV con BOM para que Excel respete los acentos. Sin el texto de las preguntas salvo que se pida
    explícitamente: pueden contener datos personales."""
    columns = CSV_COLUMNS + (["question"] if include_questions else [])
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(columns)
    for row in rows:
        values = {
            "id": row.id,
            "created_at": _iso(row),
            "artifact": names.get(row.artifact_id or ""),
            "mode": row.mode,
            "model": row.model,
            "prompt_tokens": row.prompt_tokens,
            "completion_tokens": row.completion_tokens,
            "reasoning_tokens": row.reasoning_tokens,
            "cost_usd": float(row.cost_usd or 0),
            "cost_estimated": bool(row.cost_estimated),
            "latency_ms": row.latency_ms,
            "outcome": row.outcome,
            "reject_reason": row.reject_reason,
            "rating": row.rating,
            "question": row.question,
        }
        writer.writerow([_safe(values[c]) if isinstance(values[c], str | type(None)) else values[c] for c in columns])
    return "﻿" + buffer.getvalue()
