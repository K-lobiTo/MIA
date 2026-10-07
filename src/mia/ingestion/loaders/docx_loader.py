from collections.abc import Iterator
from pathlib import Path

from docx import Document as DocxDocument
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

from mia.ingestion.loaders.base import DocumentLoader


class DocxLoader(DocumentLoader):
    def load(self, path: Path) -> str:
        doc = DocxDocument(str(path))
        return "\n".join(_blocks(doc.element.body, doc))


def _blocks(container, parent) -> Iterator[str]:
    """Párrafos y tablas en el orden del documento. Los programas de curso del TEC tienen casi
    todo su contenido (datos generales, objetivos, contenidos, evaluación) en tablas, que
    `doc.paragraphs` no incluye."""
    for child in container.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, parent).text
        elif child.tag == qn("w:tbl"):
            yield from _table_rows(Table(child, parent))


def _table_rows(table: Table) -> Iterator[str]:
    # Una fila por línea, con las celdas separadas por " | ". Una celda combinada aparece repetida
    # en `row.cells`, así que se toma una sola vez. Las tablas anidadas se leen dentro de su celda.
    for row in table.rows:
        cells: list[str] = []
        seen = set()
        for cell in row.cells:
            if cell._tc in seen:
                continue
            seen.add(cell._tc)
            text = "\n".join(line for line in _blocks(cell._tc, cell) if line.strip()).strip()
            if text:
                cells.append(text)
        if cells:
            yield " | ".join(cells)
