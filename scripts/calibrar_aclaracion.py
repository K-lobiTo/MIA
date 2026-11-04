"""Calibra la aclaración de programa del bot (feature 013) con documentos reales en un Qdrant local.

Ingiere los .txt de una carpeta en una colección temporal (con el mismo modelo de embeddings de producción), recorre los casos
de `scripts/datos/casos_aclaracion.json` y para cada pregunta imprime el mejor puntaje, las palabras con contenido y los
programas candidatos de la búsqueda de decisión (la regla de `mia.rag.programs`, con los valores de `BOT_CLARIFY_*`).

Solo las preguntas que NO pasan `QUERY_SIMILARITY_THRESHOLD` llegan a la búsqueda de decisión en la API: una que sí lo pasa
la responde el modelo y se marca "pasa el umbral". Sale con código 1 si algún caso no se comporta como espera.

    python scripts/calibrar_aclaracion.py --documentos tmp/nuevos
"""

import argparse
import json
import sys
import uuid
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from qdrant_client import QdrantClient

from mia.config import settings
from mia.ingestion.chunker import chunk_text
from mia.rag.embeddings import get_embedding_provider
from mia.rag.programs import clear_cache, content_words, group_by_program
from mia.storage.vector_store import Chunk, QdrantVectorStore

RUTA_CASOS = RAIZ / "scripts" / "datos" / "casos_aclaracion.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--documentos", required=True, help="carpeta con los .txt de los programas")
    parser.add_argument("--qdrant", default="http://localhost:6333", help="Qdrant local (colección temporal)")
    parser.add_argument("--min-similitud", type=float, default=settings.bot_clarify_min_similarity)
    parser.add_argument("--candidatos", type=int, default=settings.bot_clarify_candidates)
    parser.add_argument("--max-programas", type=int, default=settings.bot_clarify_max_programs)
    args = parser.parse_args()

    casos = json.loads(RUTA_CASOS.read_text(encoding="utf-8"))
    archivos = sorted(Path(args.documentos).glob("*.txt"))
    if not archivos:
        print(f"No hay .txt en {args.documentos}", file=sys.stderr)
        return 2
    embeddings = get_embedding_provider(settings.embedding_provider)
    coleccion = "mia_calibracion_" + uuid.uuid4().hex[:6]
    almacen = QdrantVectorStore(url=args.qdrant, collection=coleccion)
    almacen.ensure_collection(embeddings.dimension)
    fallos = 0
    try:
        for archivo in archivos:
            trozos = chunk_text(archivo.read_text(encoding="utf-8"))
            vectores = embeddings.embed(trozos, is_query=False)
            almacen.upsert(
                [
                    Chunk(id=str(uuid.uuid4()), document_id=archivo.stem, domain="d", text=t, chunk_index=i, embedding=v)
                    for i, (t, v) in enumerate(zip(trozos, vectores, strict=True))
                ]
            )
        print(f"{len(archivos)} documentos; umbral {settings.query_similarity_threshold}, piso {args.min_similitud}, candidatos {args.candidatos}\n")
        for caso in casos:
            clear_cache()
            vector = embeddings.embed([caso["pregunta"]], is_query=True)[0]
            resultados = almacen.search(vector, domains=["d"], limit=args.candidatos)
            mejor = resultados[0].score if resultados else 0.0
            palabras = content_words(caso["pregunta"])
            programas = group_by_program(resultados, almacen, args.min_similitud, args.max_programas, evidence_words=palabras)
            pasa = mejor >= settings.query_similarity_threshold
            pregunta_aclaracion = len(programas) >= 2
            if pasa:
                resultado = "pasa el umbral (la responde el modelo)"
                bien = True
            else:
                resultado = "ACLARACIÓN" if pregunta_aclaracion else "sin información"
                bien = pregunta_aclaracion == (caso["espera"] == "aclaracion")
            fallos += 0 if bien else 1
            nombres = ", ".join(p.name.split(" (")[0] for p in programas) or "ninguno"
            print(f"{'ok ' if bien else 'MAL'} {caso['id']:4s} {mejor:.3f} {resultado:40s} palabras={palabras} programas: {nombres}")
            print(f"       {caso['pregunta']}  [espera {caso['espera']}]")
    finally:
        QdrantClient(url=args.qdrant).delete_collection(coleccion)
    print(f"\n{'Todos los casos se comportan como se espera.' if not fallos else f'{fallos} caso(s) no se comportan como se espera.'}")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
