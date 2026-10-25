"""Validación de las imágenes de documentos por su contenido (feature 011, research R5 de specs/011-bot-whatsapp-kapso).

Solo se aceptan PNG y JPG (los formatos que admite WhatsApp). Manda el contenido: la firma del archivo y su final, no el
nombre ni el tipo que declara el navegador. Comprobar la firma rechaza un archivo de otro formato aunque se llame `.png`,
y comprobar el final rechaza una imagen cortada o dañada, sin sumar una biblioteca de imágenes (Pillow) ni memoria a una
API que está al límite. Puro: sin FastAPI ni base de datos.
"""

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
JPEG_SIGNATURE = b"\xff\xd8\xff"
JPEG_END = b"\xff\xd9"
# El último trozo de un PNG es IEND: 4 bytes de largo (0), el nombre y 4 bytes de CRC.
PNG_END_NAME = b"IEND"

CONTENT_TYPE_PNG = "image/png"
CONTENT_TYPE_JPEG = "image/jpeg"

# Largo máximo de la descripción (pie de foto) de una imagen.
MAX_CAPTION = 1000


class ImageError(ValueError):
    """La imagen no se puede aceptar."""


class ImageFormatError(ImageError):
    """No es un PNG ni un JPG."""


class ImageIncompleteError(ImageError):
    """Tiene la firma de un PNG o un JPG pero está incompleta o dañada."""


def validate_image(content: bytes) -> str:
    """El tipo (`image/png` o `image/jpeg`) de la imagen, o un error si no es un PNG o JPG completo."""
    if content.startswith(PNG_SIGNATURE):
        if len(content) < 20 or content[-8:-4] != PNG_END_NAME:
            raise ImageIncompleteError("La imagen está incompleta o dañada.")
        return CONTENT_TYPE_PNG
    if content.startswith(JPEG_SIGNATURE):
        if len(content) < 5 or not content.endswith(JPEG_END):
            raise ImageIncompleteError("La imagen está incompleta o dañada.")
        return CONTENT_TYPE_JPEG
    raise ImageFormatError("Solo se aceptan imágenes PNG o JPG.")
