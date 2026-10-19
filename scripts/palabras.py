"""Prepara el índice de texto de Qdrant para la búsqueda híbrida (feature 010).

La búsqueda por palabras usa un índice de texto sobre el campo `text` de los fragmentos. Crearlo sobre una
colección que ya tiene documentos es una operación de Qdrant: no recalcula vectores, no usa modelos ni gasta
tokens, se puede repetir sin duplicar nada y se revierte quitando el índice (los vectores y el texto no se
tocan). Los documentos que se ingieran después entran al índice con la ingesta normal.

Uso (ver "Búsqueda híbrida" en docs/OPERACION.md):
    python scripts/palabras.py estado                                # solo lectura
    python scripts/palabras.py preparar                              # crea el índice (pide confirmación)
    python scripts/palabras.py quitar                                # quita el índice (pide confirmación)
    python scripts/palabras.py --env-file .env.produccion estado     # contra el Qdrant de producción

`preparar` y `quitar` escriben en el Qdrant del archivo de entorno: muestran el destino y piden confirmación
(`--si` la salta).
"""

import argparse
import os
import sys


def _cargar_entorno(ruta: str) -> None:
    """Carga un archivo de variables (p. ej. .env.produccion) antes de importar la configuración."""
    from dotenv import dotenv_values

    valores = dotenv_values(ruta)
    if not valores:
        raise ValueError(f"No se pudo leer el archivo de entorno {ruta}.")
    for clave, valor in valores.items():
        if valor is not None:
            os.environ[clave] = valor


def _almacen_y_destino():
    # La configuración se lee al importar, por eso este import va después de cargar el entorno.
    from mia.config import settings
    from mia.storage.vector_store import get_vector_store

    return get_vector_store(), f"{settings.qdrant_url} (colección {settings.qdrant_collection})"


def _mostrar_estado(almacen) -> dict:
    estado = almacen.text_index_status()
    if not estado["exists"]:
        print("Índice de texto: no existe.")
    else:
        params = estado["params"]
        print(
            f"Índice de texto: existe (tokenizador {params.get('tokenizer')}, palabras de "
            f"{params.get('min_token_len')} a {params.get('max_token_len')} letras)."
        )
        print(f"Fragmentos indexados: {estado['indexed']} de {estado['points']}.")
    return estado


def ejecutar(args, almacen, destino: str, entrada=input) -> int:
    print(f"Destino: {destino}")
    try:
        if args.orden == "estado":
            _mostrar_estado(almacen)
            return 0
        accion = "crear" if args.orden == "preparar" else "quitar"
        if not args.si and entrada(f"Vas a {accion} el índice de texto en {destino}. ¿Continuar? [s/N] ").strip().lower() != "s":
            print("No se hizo nada.")
            return 0
        if args.orden == "preparar":
            almacen.ensure_text_index()
            print("Listo: el índice de texto quedó creado.")
        else:
            almacen.drop_text_index()
            print("Listo: el índice de texto se quitó. Los vectores y el texto no se tocaron.")
        _mostrar_estado(almacen)
        return 0
    except Exception as error:  # noqa: BLE001 (un script de operación debe mostrar cualquier error de Qdrant)
        print(f"Error: {type(error).__name__}: {error}", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None, almacen_y_destino=None, entrada=input) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--env-file", help="archivo de variables (p. ej. .env.produccion) con QDRANT_URL y la colección")
    parser.add_argument("--si", action="store_true", help="no pedir confirmación en preparar y quitar")
    ordenes = parser.add_subparsers(dest="orden", required=True)
    ordenes.add_parser("estado", help="muestra si el índice existe y cuántos fragmentos tiene indexados")
    ordenes.add_parser("preparar", help="crea el índice de texto (idempotente)")
    ordenes.add_parser("quitar", help="quita el índice de texto")
    args = parser.parse_args(argv)

    if almacen_y_destino is None:
        if args.env_file:
            try:
                _cargar_entorno(args.env_file)
            except ValueError as error:
                print(f"Error: {error}", file=sys.stderr)
                return 1
        almacen_y_destino = _almacen_y_destino
    almacen, destino = almacen_y_destino()
    return ejecutar(args, almacen, destino, entrada)


if __name__ == "__main__":
    sys.exit(main())
