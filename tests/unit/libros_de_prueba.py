"""Libros de Excel armados con openpyxl para las pruebas de la feature 018 (no se guardan binarios en el repositorio)."""

from pathlib import Path

from openpyxl import Workbook


def hacer_libro(ruta: Path, hojas: dict[str, list[list]]) -> Path:
    """Guarda un .xlsx con una hoja por clave (nombre de la hoja a lista de filas) y devuelve la ruta."""
    libro = Workbook()
    libro.remove(libro.active)
    for nombre, filas in hojas.items():
        hoja = libro.create_sheet(nombre)
        for fila in filas:
            hoja.append(fila)
    libro.save(ruta)
    return ruta


def libro_de_cursos(ruta: Path) -> Path:
    return hacer_libro(
        ruta,
        {
            "Cursos": [
                ["Código", "Nombre", "Créditos", "Profesor"],
                ["MC4001", "Redes seguras", 3, "Ana Mora"],
                ["MC4002", "Criptografía", 4, "Luis Rojas"],
            ]
        },
    )
