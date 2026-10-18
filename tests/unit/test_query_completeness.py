from unittest.mock import MagicMock, patch

import pytest

from mia.api.routes import query as query_routes
from mia.config import settings
from mia.rag import citations, completeness
from mia.rag.llm import LLMAnswer
from mia.storage.models import Document, Domain, QueryLog, Unit
from mia.storage.vector_store import SearchResult


@pytest.fixture
def base(db, modes_config):
    with db() as session:
        session.add(Unit(id="u1", name="Computación"))
        session.flush()
        session.add(Domain(id="dom-1", unit_id="u1", name="Currículum", description=""))
        session.flush()
        for numero in (1, 2, 3):
            session.add(
                Document(
                    id=f"doc-{numero}", domain_id="dom-1", filename=f"curso-{numero}.pdf", source_type="pdf",
                    file_hash=f"h{numero}", status="done",
                )
            )
        session.commit()
