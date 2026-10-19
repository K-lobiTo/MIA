"""Copia una colección de Qdrant (puntos con sus vectores y su payload) a un Qdrant local (feature 010).

Sirve para calibrar la búsqueda híbrida con los datos de producción sin escribir en producción: el origen se lee
solo con `scroll` y `get_collection` (cualquier otra operación se rechaza) y el destino es un Qdrant de desarrollo.
Repetir la copia no duplica nada (conserva los ids de los puntos). No usa modelos ni gasta tokens.

Uso:
    python scripts/copiar_coleccion.py --origen-env .env.produccion --destino-coleccion mia_hibrida --indice

Después, para medir contra la copia: QDRANT_URL=http://localhost:6333 y QDRANT_COLLECTION=mia_hibrida en el entorno
local, y `python scripts/linea_base.py puntajes --palabras ...`.
"""

import argparse
import sys

LOTE = 500
PERMITIDOS = frozenset({"scroll", "get_collection", "collection_exists", "count"})


class SoloLectura:
    """Envuelve el cliente de Qdrant del origen y solo deja pasar las operaciones de lectura."""

    def __init__(self, cliente):
        self._cliente = cliente

    def __getattr__(self, nombre):
        if nombre not in PERMITIDOS:
            raise PermissionError(f"Operación no permitida en el origen (solo lectura): {nombre}")
        return getattr(self._cliente, nombre)


def _cargar_entorno(ruta: str) -> dict:
    from dotenv import dotenv_values

    valores = {k: v for k, v in dotenv_values(ruta).items() if v is not None}
    if not valores:
        raise ValueError(f"No se pudo leer el archivo de entorno {ruta}.")
    return valores


def _mismo_destino(url_a: str, coleccion_a: str, url_b: str, coleccion_b: str) -> bool:
    return url_a.rstrip("/") == url_b.rstrip("/") and coleccion_a == coleccion_b


def copiar(origen, destino, coleccion_origen: str, coleccion_destino: str, indice: bool = False, lote: int = LOTE,
           mostrar=print) -> dict:
    """Copia todos los puntos de `coleccion_origen` (en `origen`, solo lectura) a `coleccion_destino` (en `destino`)."""
    from qdrant_client.models import PointStruct, VectorParams

    from mia.storage.vector_store import FILTERABLE_FIELDS

    origen = origen if isinstance(origen, SoloLectura) else SoloLectura(origen)
    info = origen.get_collection(coleccion_origen)
    vectores = info.config.params.vectors
    esperados = info.points_count
    if not destino.collection_exists(coleccion_destino):
        destino.create_collection(
            collection_name=coleccion_destino, vectors_config=VectorParams(size=vectores.size, distance=vectores.distance)
        )
        mostrar(f"Colección de destino creada ({vectores.size} dimensiones, {vectores.distance}).")
    copiados, desplazamiento = 0, None
    while True:
        puntos, desplazamiento = origen.scroll(
            collection_name=coleccion_origen, limit=lote, offset=desplazamiento, with_payload=True, with_vectors=True
        )
        if puntos:
            destino.upsert(
                collection_name=coleccion_destino,
                points=[PointStruct(id=p.id, vector=p.vector, payload=p.payload) for p in puntos],
            )
            copiados += len(puntos)
            mostrar(f"  {copiados} de {esperados} puntos copiados")
        if desplazamiento is None:
            break
    for campo, esquema in FILTERABLE_FIELDS.items():
        destino.create_payload_index(collection_name=coleccion_destino, field_name=campo, field_schema=esquema)
    if indice:
        from mia.storage.vector_store import TEXT_FIELD, TEXT_INDEX_PARAMS

        destino.create_payload_index(
            collection_name=coleccion_destino, field_name=TEXT_FIELD, field_schema=TEXT_INDEX_PARAMS, wait=True
        )
        mostrar("Índice de texto creado en el destino.")
    en_destino = destino.count(collection_name=coleccion_destino, exact=True).count
    return {"origen": esperados, "copiados": copiados, "destino": en_destino}


def main(argv: list[str] | None = None, clientes=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--origen-env", required=True, help="archivo de entorno del origen (p. ej. .env.produccion)")
    parser.add_argument("--destino-url", default="http://localhost:6333")
    parser.add_argument("--destino-coleccion", required=True)
    parser.add_argument("--indice", action="store_true", help="crea también el índice de texto en el destino")
    args = parser.parse_args(argv)

    try:
        entorno = _cargar_entorno(args.origen_env)
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    url_origen = entorno.get("QDRANT_URL", "")
    coleccion_origen = entorno.get("QDRANT_COLLECTION", "mia_chunks")
    if not url_origen:
        print(f"Error: {args.origen_env} no define QDRANT_URL.", file=sys.stderr)
        return 1
    if _mismo_destino(url_origen, coleccion_origen, args.destino_url, args.destino_coleccion):
        print("Error: el destino es el mismo Qdrant y la misma colección que el origen. No se copia.", file=sys.stderr)
        return 1
    if clientes is None:
        from qdrant_client import QdrantClient

        origen = QdrantClient(url=url_origen, api_key=entorno.get("QDRANT_API_KEY") or None, timeout=60)
        destino = QdrantClient(url=args.destino_url, timeout=60)
    else:
        origen, destino = clientes
    print(f"Origen (solo lectura): {url_origen} (colección {coleccion_origen})")
    print(f"Destino: {args.destino_url} (colección {args.destino_coleccion})")
    try:
        resultado = copiar(origen, destino, coleccion_origen, args.destino_coleccion, indice=args.indice)
    except Exception as error:  # noqa: BLE001 (un script de operación debe mostrar cualquier error de Qdrant)
        print(f"Error: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    print(f"Listo: {resultado['copiados']} puntos copiados; el destino tiene {resultado['destino']} de {resultado['origen']}.")
    return 0 if resultado["destino"] >= resultado["origen"] else 1


if __name__ == "__main__":
    sys.exit(main())
