from pathlib import Path

from pypdf import PdfReader

from mia.ingestion.loaders.base import DocumentLoader


class PdfLoader(DocumentLoader):
    def load(self, path: Path) -> str:
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
