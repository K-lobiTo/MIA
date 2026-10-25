"""Bytes de imágenes de prueba (feature 011), armados aquí para no guardar archivos binarios en el repositorio."""

PNG_SIGNATURE = bytes.fromhex("89504e470d0a1a0a")
IEND = bytes.fromhex("0000000049454e44ae426082")

# Un PNG de 1x1 píxel completo (firma, IHDR, IDAT, IEND).
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000a49444154789c6360000002000001e221bc33"
    "0000000049454e44ae426082"
)
# Un JPEG mínimo: empieza con FF D8 FF y termina con FF D9.
JPEG = bytes.fromhex("ffd8ffe000104a46494600010100000100010000ffd9")

GIF = b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00;"
WEBP = b"RIFF\x1a\x00\x00\x00WEBPVP8 \x0e\x00\x00\x00"
PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"


def png_of_size(size: int) -> bytes:
    """Un PNG que pasa la validación (firma e IEND al final) de exactamente `size` bytes, para probar el tamaño máximo."""
    padding = size - len(PNG_SIGNATURE) - len(IEND)
    assert padding >= 0
    return PNG_SIGNATURE + b"\x00" * padding + IEND


def jpeg_of_size(size: int) -> bytes:
    padding = size - 5
    assert padding >= 0
    return b"\xff\xd8\xff" + b"\x00" * padding + b"\xff\xd9"
