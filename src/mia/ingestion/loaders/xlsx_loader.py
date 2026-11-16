"""Cargador de libros de Excel (.xlsx), feature 018.

Convierte el libro en texto plano para el resto del pipeline: una línea por fila, con el nombre de la hoja al inicio de
cada línea (`[Cursos] ...`), para que cualquier fragmento que contenga una fila sea autosuficiente (research R2 y R3).
Se lee con `openpyxl` en modo de solo lectura y solo valores: no ejecuta macros ni resuelve vínculos externos (FR-011) y
entrega el último resultado guardado de las fórmulas, nunca su expresión (research R1).
"""

from datetime import date, datetime
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from mia.config import settings
from mia.ingestion.loaders.base import DocumentLoader, LoaderError

ERROR_ILEGIBLE = "No se pudo leer el libro: el archivo está dañado o protegido con contraseña."
ERROR_SIN_CONTENIDO = "El libro no tiene hojas visibles con contenido."

# Una hoja puede declarar un área usada enorme solo por tener una celda con formato muy lejos (el Ctrl+Fin de Excel llega a
# XFD1048576). `openpyxl` rellena cada fila hasta el ancho declarado, así que sin límites una celda en XFD50000 tardaba 92 s
# (medido el 2026-11-15). Se leen como máximo estas columnas y se deja de leer la hoja tras estas filas vacías seguidas
# (research R9).
MAX_COLUMNAS = 200
MAX_FILAS_VACIAS_SEGUIDAS = 10000


class XlsxLoader(DocumentLoader):
    def load(self, path: Path) -> str:
        self.notes = []
        try:
            workbook = load_workbook(path, read_only=True, data_only=True)
            try:
                lineas, corte, avisos = _lineas_del_libro(workbook, settings.max_excel_rows)
            finally:
                workbook.close()
        except Exception:  # noqa: BLE001
            # Libro dañado, con contraseña (no es un zip) o con XML corrupto: un mensaje fijo, sin detalles del archivo.
            raise LoaderError(ERROR_ILEGIBLE) from None
        if not lineas:
            raise LoaderError(ERROR_SIN_CONTENIDO)
        if corte is not None:
            hoja, fila = corte
            avisos.append(
                f'el libro se recortó en la fila {fila} de la hoja "{hoja}" por superar el tope de {settings.max_excel_rows} filas'
            )
        for detalle in avisos:
            # El aviso también queda en el texto para que una respuesta no presente el libro como completo (FR-008).
            lineas.append(f"[Aviso: {detalle}]")
            self.notes.append(detalle[0].upper() + detalle[1:] + ".")
        return "\n".join(lineas)


def _lineas_del_libro(workbook, limite: int) -> tuple[list[str], tuple[str, int] | None, list[str]]:
    """Líneas de todas las hojas visibles, (hoja, fila) donde se cortó por el tope de filas si ocurrió y los avisos de los
    límites de lectura de cada hoja (columnas y filas vacías). Las hojas ocultas se ignoran; las de gráfico no están en
    `worksheets` (FR-004)."""
    lineas: list[str] = []
    avisos: list[str] = []
    escritas = 0
    for hoja in workbook.worksheets:
        if hoja.sheet_state != "visible":
            continue
        filas, escritas, corte, avisos_de_hoja = _lineas_de_hoja(hoja, escritas, limite)
        if filas:
            lineas.append(f"## Hoja: {hoja.title}")
            lineas.extend(filas)
        avisos.extend(avisos_de_hoja)
        if corte is not None:
            return lineas, (hoja.title, corte), avisos
    return lineas, None, avisos


ERRORES_DE_EXCEL = {"#DIV/0!", "#N/A", "#REF!", "#VALUE!", "#NAME?", "#NUM!", "#NULL!"}


def _texto_de_celda(valor, formato: str | None = None) -> str | None:
    """Texto de una celda tal como lo ve la persona, o None si está vacía o es un error de Excel (research R4). No se
    reproducen símbolos de moneda ni separadores de miles: el valor se conserva exacto."""
    if valor is None:
        return None
    if isinstance(valor, bool):
        return "Sí" if valor else "No"
    if isinstance(valor, datetime):
        texto = valor.strftime("%d/%m/%Y")
        return texto if (valor.hour, valor.minute, valor.second) == (0, 0, 0) else f"{texto} {valor:%H:%M}"
    if isinstance(valor, date):
        return valor.strftime("%d/%m/%Y")
    if isinstance(valor, (int, float)):
        if "%" in (formato or ""):
            return _numero(round(valor * 100, 10)) + "%"
        return _numero(valor)
    texto = " ".join(str(valor).split())  # los saltos de línea internos se vuelven espacios
    if not texto or texto in ERRORES_DE_EXCEL:
        return None
    return texto


def _numero(valor: float) -> str:
    if isinstance(valor, float) and valor == int(valor):
        return str(int(valor))
    return str(valor)


def _nombres_de_columnas(fila: list[str | None]) -> list[str]:
    """Encabezado de cada columna: el texto de la celda, `Columna <LETRA>` si está vacía y, si se repite, el segundo y los
    siguientes llevan la letra de su columna entre paréntesis (research R3)."""
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


def _lineas_de_hoja(hoja, escritas: int, limite: int) -> tuple[list[str], int, int | None, list[str]]:
    """Una línea por fila con contenido. Las filas anteriores a la de encabezados (títulos, notas) van como texto simple;
    la fila de encabezados es la primera con al menos dos celdas con contenido y no se escribe ni cuenta para el tope. Sin
    una fila así (hoja de una columna) no hay encabezados. En modo de solo lectura las celdas combinadas solo traen el valor
    en la celda superior izquierda y las demás llegan vacías, así que el valor aparece una sola vez (FR-006).

    Devuelve (líneas, filas escritas en total, número de fila donde se cortó o None, avisos). Se corta solo si existe una
    fila más con contenido después de `limite` filas escritas. Los avisos dicen cuándo los límites de lectura de R9 dejaron
    contenido sin leer, para no recortar en silencio (FR-008)."""
    prefijo = f"[{hoja.title}] "
    lineas: list[str] = []
    encabezados: list[str] | None = None
    avisos: list[str] = []
    columnas_cortadas = False
    numero = 0
    vacias_seguidas = 0
    # Se lee una columna de más solo para saber si hay contenido más allá del tope.
    for fila in hoja.iter_rows(max_col=MAX_COLUMNAS + 1):
        numero = _numero_de_fila(fila, numero)
        # En modo de solo lectura las celdas de relleno son `EmptyCell` (sin `value` ni `number_format`).
        textos = [_texto_de_celda(getattr(c, "value", None), getattr(c, "number_format", None)) for c in fila]
        if len(textos) > MAX_COLUMNAS:
            if textos[MAX_COLUMNAS] and not columnas_cortadas:
                columnas_cortadas = True
                avisos.append(f'en la hoja "{hoja.title}" se leyeron solo las primeras {MAX_COLUMNAS} columnas')
            textos = textos[:MAX_COLUMNAS]
        con_contenido = [texto for texto in textos if texto]
        if not con_contenido:
            vacias_seguidas += 1
            if vacias_seguidas >= MAX_FILAS_VACIAS_SEGUIDAS:
                # No se sabe si había datos después sin leerlos: se avisa siempre que el corte ocurre.
                avisos.append(
                    f'se dejó de leer la hoja "{hoja.title}" en la fila {numero} tras {MAX_FILAS_VACIAS_SEGUIDAS} filas '
                    "vacías seguidas; si había datos después, no se ingestaron"
                )
                break
            continue
        vacias_seguidas = 0
        if encabezados is None and len(con_contenido) >= 2:
            encabezados = _nombres_de_columnas(textos)
            continue
        if escritas >= limite:
            return lineas, escritas, numero, avisos
        escritas += 1
        if encabezados is None:
            lineas.append(prefijo + " | ".join(con_contenido))
        else:
            # Todas las filas llegan rellenadas al mismo ancho, así que cada columna tiene su encabezado.
            pares = [f"{encabezados[i]}: {texto}" for i, texto in enumerate(textos) if texto]
            lineas.append(prefijo + " | ".join(pares))
    return lineas, escritas, None, avisos


def _numero_de_fila(fila, anterior: int) -> int:
    for celda in fila:
        numero = getattr(celda, "row", None)
        if numero:
            return numero
    return anterior + 1
