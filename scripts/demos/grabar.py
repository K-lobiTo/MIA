"""SOLO DESARROLLO: graba uno o más videos de la guía de uso.

Requiere el servidor de datos ficticios (`servidor_demo.py`) y los dos sitios en modo desarrollo (ver docs/demos/README.md).

    python scripts/demos/grabar.py a3-preguntar            # un video
    python scripts/demos/grabar.py --lista                 # los que hay
"""

import argparse
import importlib
import pkgutil
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import guiones
from grabador import Grabacion

SALIDA = AQUI.parents[1] / "docs" / "demos" / "clips"


def cargar() -> dict:
    modulos = {}
    for info in pkgutil.iter_modules(guiones.__path__):
        mod = importlib.import_module(f"guiones.{info.name}")
        modulos[mod.ID] = mod
    return modulos


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("videos", nargs="*", help="identificadores de los videos a grabar")
    parser.add_argument("--lista", action="store_true")
    parser.add_argument("--tema", choices=["light", "dark"], default="light")
    args = parser.parse_args()
    modulos = cargar()
    if args.lista or not args.videos:
        for id_, mod in sorted(modulos.items()):
            print(f"{id_}: {mod.TITULO}")
        return 0
    for id_ in args.videos:
        mod = modulos[id_]
        with Grabacion(
            mod.ID, mod.TITULO, SALIDA, mod.URL,
            storage=getattr(mod, "STORAGE", None), tema=args.tema, ignorar_https=getattr(mod, "IGNORAR_HTTPS", False),
        ) as g:
            mod.guion(g)
    return 0


if __name__ == "__main__":
    sys.exit(main())
