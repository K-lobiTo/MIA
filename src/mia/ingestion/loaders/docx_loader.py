from pathlib import Path

from docx import Document as DocxDocument

from mia.ingestion.loaders.base import DocumentLoader


class DocxLoader(DocumentLoader):
    def load(self, path: Path) -> str:
        doc = DocxDocument(str(path))
        return "\n".join(p.text for p in doc.paragraphs)
