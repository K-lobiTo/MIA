"""SOLO DESARROLLO: crea los archivos de ejemplo de `datos_demo/` (Excel y CSV con datos inventados).

    python scripts/demos/crear_datos.py     (con el entorno de MIA: usa openpyxl)

El CSV se guarda en Windows-1252 con punto y coma, como lo exporta Excel en español: así el video muestra que MIA lo lee
sin que la persona lo prepare. El CSV vacío sirve para mostrar el aviso de un documento con error.
"""

from pathlib import Path

from openpyxl import Workbook

DESTINO = Path(__file__).resolve().parent / "datos_demo"

CURSOS = [
    ("Código", "Curso", "Créditos", "Horas extraclase"),
    ("EJ-101", "Taller de Ejemplo A", 3, 6),
    ("EJ-102", "Taller de Ejemplo B", 4, 8),
    ("EJ-201", "Seminario de Ejemplo", 2, 4),
]


def main() -> None:
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Cursos"
    for fila in CURSOS:
        hoja.append(fila)
    libro.save(DESTINO / "Cursos de ejemplo.xlsx")

    lineas = [";".join(str(c) for c in fila) for fila in CURSOS]
    (DESTINO / "Cursos de ejemplo.csv").write_bytes(("\r\n".join(lineas) + "\r\n").encode("cp1252"))
    (DESTINO / "Archivo vacio de ejemplo.csv").write_bytes(b"")
    for nombre in ("Cursos de ejemplo.xlsx", "Cursos de ejemplo.csv", "Archivo vacio de ejemplo.csv"):
        print("creado", DESTINO / nombre)


if __name__ == "__main__":
    main()
