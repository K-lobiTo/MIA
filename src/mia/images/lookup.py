"""Las imágenes de los documentos de las fuentes de una respuesta (feature 011, research R6).

Una sola consulta a la base, sin leer los binarios: solo el id público, la descripción y la posición. El orden es el de
los documentos dados (el de las fuentes de la respuesta, cada documento una vez) y, dentro de un documento, el de su posición.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from mia.storage.models import DocumentImage


@dataclass(frozen=True)
class ImageRef:
    document_id: str
    public_id: str
    caption: str
    position: int


def images_for_documents(session: Session, document_ids: list[str]) -> list[ImageRef]:
    """Las imágenes de los documentos, en el orden de `document_ids` (sin repetir documentos) y por posición."""
    ordered = list(dict.fromkeys(document_ids))
    if not ordered:
        return []
    rows = session.execute(
        select(
            DocumentImage.document_id, DocumentImage.public_id, DocumentImage.caption, DocumentImage.position
        ).where(DocumentImage.document_id.in_(ordered))
    ).all()
    by_document: dict[str, list[ImageRef]] = {}
    for row in sorted(rows, key=lambda r: r.position):
        by_document.setdefault(row.document_id, []).append(
            ImageRef(row.document_id, row.public_id, row.caption, row.position)
        )
    return [ref for document_id in ordered for ref in by_document.get(document_id, [])]
