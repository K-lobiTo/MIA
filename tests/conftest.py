import os
import tempfile

# Los tests no deben depender del .env de quien los corre (que puede apuntar a bases de
# producción): se fijan valores locales antes de que se importe mia.config.
os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/test.db"
os.environ["QDRANT_URL"] = "http://localhost:6333"
os.environ["QDRANT_API_KEY"] = ""
os.environ["INGESTION_ENABLED"] = "true"

from mia.storage.db import init_db

init_db()
