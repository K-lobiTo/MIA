from abc import ABC, abstractmethod
from pathlib import Path


class LoaderError(Exception):
    """Falla con un mensaje pensado para la persona administradora (se guarda como nota del documento)."""


class DocumentLoader(ABC):
    def __init__(self) -> None:
        # Avisos no fatales de la última lectura (por ejemplo, un libro recortado). Vacío por defecto.
        self.notes: list[str] = []

    @abstractmethod
    def load(self, path: Path) -> str:
        """Devuelve el texto plano extraído del archivo."""
        ...


def get_loader(source_type: str) -> DocumentLoader:
    if source_type == "pdf":
        from mia.ingestion.loaders.pdf_loader import PdfLoader

        return PdfLoader()
    if source_type == "docx":
        from mia.ingestion.loaders.docx_loader import DocxLoader

        return DocxLoader()
    if source_type == "xlsx":
        from mia.ingestion.loaders.xlsx_loader import XlsxLoader

        return XlsxLoader()
    if source_type == "csv":
        from mia.ingestion.loaders.csv_loader import CsvLoader

        return CsvLoader()
    if source_type == "web":
        from mia.ingestion.loaders.web_loader import WebLoader

        return WebLoader()
    if source_type == "txt":
        from mia.ingestion.loaders.txt_loader import TxtLoader

        return TxtLoader()
    raise ValueError(f"Tipo de fuente no soportado: {source_type}")
