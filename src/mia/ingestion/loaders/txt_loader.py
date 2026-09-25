from pathlib import Path

from mia.ingestion.loaders.base import DocumentLoader


class TxtLoader(DocumentLoader):
    def load(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")
