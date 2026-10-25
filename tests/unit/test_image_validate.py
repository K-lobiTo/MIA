"""Validación de las imágenes de documentos por su contenido (feature 011, research R5)."""

import pytest

from mia.images.validate import ImageFormatError, ImageIncompleteError, validate_image
from tests.unit.imagenes_de_prueba import (
    GIF,
    IEND,
    JPEG,
    PDF,
    PNG,
    PNG_SIGNATURE,
    WEBP,
    jpeg_of_size,
    png_of_size,
)


def test_un_png_completo_es_image_png():
    assert validate_image(PNG) == "image/png"


def test_un_jpeg_completo_es_image_jpeg():
    assert validate_image(JPEG) == "image/jpeg"


def test_el_tamano_no_importa_para_la_validacion_de_formato():
    assert validate_image(png_of_size(3 * 1024 * 1024)) == "image/png"
    assert validate_image(jpeg_of_size(100)) == "image/jpeg"


@pytest.mark.parametrize("contenido", [GIF, WEBP, PDF, b"texto cualquiera", b"<svg></svg>", b"", b"\x00" * 20])
def test_otro_formato_es_error_de_formato_aunque_se_llame_png(contenido):
    # Manda el contenido: el nombre del archivo ni el tipo que declara el navegador cuentan, así que ni se reciben.
    with pytest.raises(ImageFormatError):
        validate_image(contenido)


def test_un_png_sin_el_trozo_iend_final_esta_incompleto():
    with pytest.raises(ImageIncompleteError):
        validate_image(PNG[: -len(IEND)])
    with pytest.raises(ImageIncompleteError):
        validate_image(PNG[:40])


def test_solo_la_firma_de_un_png_esta_incompleta():
    with pytest.raises(ImageIncompleteError):
        validate_image(PNG_SIGNATURE)


def test_un_jpeg_sin_el_marcador_final_esta_incompleto():
    with pytest.raises(ImageIncompleteError):
        validate_image(JPEG[:-2])
    with pytest.raises(ImageIncompleteError):
        validate_image(b"\xff\xd8\xff")


def test_un_png_con_datos_despues_de_iend_esta_incompleto_o_danado():
    with pytest.raises(ImageIncompleteError):
        validate_image(PNG + b"basura al final")


def test_los_dos_errores_son_errores_de_imagen():
    from mia.images.validate import ImageError

    assert issubclass(ImageFormatError, ImageError) and issubclass(ImageIncompleteError, ImageError)
