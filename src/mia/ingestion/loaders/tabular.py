"""Lógica de filas compartida por los cargadores de tablas: el de libros de Excel (feature 018) y el de CSV (feature 021).

Convierte filas ya leídas a texto en una línea por fila, con cada valor acompañado del encabezado de su columna, y aplica los
límites de lectura con avisos visibles. No sabe de dónde vienen las filas (una hoja de `openpyxl` o los registros de un CSV):
quien la llama las convierte a texto y le da el prefijo de cada línea y el nombre del origen para redactar los avisos. Mantenerla
en un solo lugar garantiza que Excel y CSV produzcan exactamente el mismo texto de fila (research R1 de la feature 021)."""

from collections.abc import Iterable

from openpyxl.utils import get_column_letter

# Una hoja puede declarar un área usada enorme solo por tener una celda con formato muy lejos (el Ctrl+Fin de Excel llega a
# XFD1048576). `openpyxl` rellena cada fila hasta el ancho declarado, así que sin límites una celda en XFD50000 tardaba 92 s
# (medido el 2026-11-15). Se leen como máximo estas columnas y se deja de leer tras estas filas vacías seguidas (feature 018,
# research R9). El CSV usa los mismos límites.
MAX_COLUMNAS = 200
MAX_FILAS_VACIAS_SEGUIDAS = 10000


def nombres_de_columnas(fila: list[str | None]) -> list[str]:
    """Encabezado de cada columna: el texto de la celda, `Columna <LETRA>` si está vacía y, si se repite, el segundo y los
    siguientes llevan la letra de su columna entre paréntesis (feature 018, research R3)."""
    nombres: list[str] = []
    vistos: set[str] = set()
    for indice, texto in enumerate(fila, start=1):
        letra = get_column_letter(indice)
        nombre = texto or f"Columna {letra}"
        if nombre in vistos:
            nombre = f"{nombre} ({letra})"
        vistos.add(nombre)
        nombres.append(nombre)
    return nombres


def lineas_de_tabla(
    prefijo: str,
    objeto: str,
    filas: Iterable[tuple[int, list[str | None]]],
    escritas: int,
    limite: int,
) -> tuple[list[str], int, int | None, list[str]]:
    """Una línea por fila con contenido. Las filas anteriores a la de encabezados (títulos, notas) van como texto simple; la
    fila de encabezados es la primera con al menos dos celdas con contenido y no se escribe ni cuenta para el tope. Sin una fila
    así (tabla de una columna) no hay encabezados. Una fila más ancha que el encabezado nombra sus celdas de más
    `Columna <LETRA>` en lugar de perderlas, y una más corta omite las que le faltan.

    `filas` son `(número de fila, textos)` con cada celda ya convertida a texto (`None` si está vacía). `prefijo` va al inicio de
    cada línea (`[Hoja] ` en Excel, vacío en CSV) y `objeto` nombra lo que se lee en los avisos (`la hoja "X"`, `el archivo`).

    Devuelve (líneas, filas escritas en total, número de fila donde se cortó o None, avisos). Se corta solo si existe una fila
    más con contenido después de `limite` filas escritas. Los avisos dicen cuándo los límites de lectura dejaron contenido sin
    leer, para no recortar en silencio."""
    lineas: list[str] = []
    encabezados: list[str] | None = None
    avisos: list[str] = []
    columnas_cortadas = False
    vacias_seguidas = 0
    for numero, textos in filas:
        if len(textos) > MAX_COLUMNAS:
            if any(textos[MAX_COLUMNAS:]) and not columnas_cortadas:
                columnas_cortadas = True
                avisos.append(f"en {objeto} se leyeron solo las primeras {MAX_COLUMNAS} columnas")
            textos = textos[:MAX_COLUMNAS]
        con_contenido = [texto for texto in textos if texto]
        if not con_contenido:
            vacias_seguidas += 1
            if vacias_seguidas >= MAX_FILAS_VACIAS_SEGUIDAS:
                # No se sabe si había datos después sin leerlos: se avisa siempre que el corte ocurre.
                avisos.append(
                    f"se dejó de leer {objeto} en la fila {numero} tras {MAX_FILAS_VACIAS_SEGUIDAS} filas "
                    "vacías seguidas; si había datos después, no se ingestaron"
                )
                break
            continue
        vacias_seguidas = 0
        if encabezados is None and len(con_contenido) >= 2:
            encabezados = nombres_de_columnas(textos)
            continue
        if escritas >= limite:
            return lineas, escritas, numero, avisos
        escritas += 1
        if encabezados is None:
            lineas.append(prefijo + " | ".join(con_contenido))
        else:
            pares = [f"{_encabezado(encabezados, i)}: {texto}" for i, texto in enumerate(textos) if texto]
            lineas.append(prefijo + " | ".join(pares))
    return lineas, escritas, None, avisos


def _encabezado(encabezados: list[str], indice: int) -> str:
    """El encabezado de la columna `indice` (desde 0); una celda más allá del encabezado se nombra por su letra."""
    return encabezados[indice] if indice < len(encabezados) else f"Columna {get_column_letter(indice + 1)}"
