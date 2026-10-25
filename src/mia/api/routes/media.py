"""GET /media/{public_id}: sirve una imagen asociada a un documento (feature 011). Es PÚBLICA, sin clave: Kapso (y Meta)
descargan la imagen de este enlace para enviarla por WhatsApp. El identificador es aleatorio y no adivinable, y cambia al
reemplazar la imagen. Contrato en specs/011-bot-whatsapp-kapso/contracts/imagenes-api.md.
"""

import re

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from mia.storage.db import get_session
from mia.storage.models import DocumentImage

router = APIRouter(tags=["media"])

# La forma de un identificador: se comprueba antes de ir a la base, para que el tráfico basura no la consulte.
PUBLIC_ID = re.compile(r"[A-Za-z0-9_-]{20,64}")


@router.get("/media/{public_id}")
def get_media(public_id: str, session: Session = Depends(get_session)) -> Response:
    if not PUBLIC_ID.fullmatch(public_id):
        raise HTTPException(status_code=404, detail="Imagen no encontrada.")
    row = session.execute(
        select(DocumentImage.content, DocumentImage.content_type).where(DocumentImage.public_id == public_id)
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Imagen no encontrada.")
    # Una hora de caché: Kapso y Meta pueden bajar la imagen una vez por envío. Reemplazar cambia el enlace, así que la caché
    # nunca sirve una imagen vigente equivocada; al quitarla puede seguir sirviéndose desde cachés externas hasta una hora.
    return Response(
        content=bytes(row.content),
        media_type=row.content_type,
        headers={"Cache-Control": "public, max-age=3600", "X-Content-Type-Options": "nosniff"},
    )
