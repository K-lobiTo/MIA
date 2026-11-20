from pathlib import Path

from mia.ingestion.loaders.base import DocumentLoader, LoaderError

SIN_CONTENIDO = "La página no tiene contenido para procesar."


class WebLoader(DocumentLoader):
    """Documento web (feature 022). No lee la red ni interpreta HTML: eso ocurrió antes, al agregar la página, y la ruta
    dejó el texto ya extraído en `uploads/<id>.web`. Aquí solo se lee ese texto, como el de un archivo de texto."""

    def load(self, path: Path) -> str:
        try:
            texto = path.read_bytes().decode("utf-8")
        except UnicodeDecodeError as exc:
            raise LoaderError(SIN_CONTENIDO) from exc
        if not texto.strip():
            raise LoaderError(SIN_CONTENIDO)
        return texto
