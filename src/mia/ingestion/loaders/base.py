from abc import ABC, abstractmethod
from pathlib import Path


class DocumentLoader(ABC):
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
    if source_type == "txt":
        from mia.ingestion.loaders.txt_loader import TxtLoader

        return TxtLoader()
    raise ValueError(f"Tipo de fuente no soportado: {source_type}")
