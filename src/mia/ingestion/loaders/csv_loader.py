"""Cargador de archivos CSV (.csv), feature 021.

Trata el CSV como una hoja de Excel sin nombre: una línea de texto por fila, con el encabezado de cada columna delante de su
valor, con la misma lógica de filas, límites y avisos que el cargador de libros de Excel (`tabular.py`, research R1 y R7). Lo
propio del CSV es leer bien el archivo: la codificación, el separador, las comillas y las celdas con saltos de línea. Nunca
ejecuta ni evalúa el contenido de una celda (FR-010).
"""

import csv
import io
import re
from collections import Counter
from pathlib import Path

from mia.config import settings
from mia.ingestion.loaders.base import DocumentLoader, LoaderError
from mia.ingestion.loaders.tabular import lineas_de_tabla

ERROR_SIN_CONTENIDO = "El archivo CSV no tiene contenido."
ERROR_ILEGIBLE = (
    "No se pudo leer el archivo: no es un CSV de texto en UTF-8 ni en Windows-1252. "
    "Guárdalo de nuevo como «CSV UTF-8» y vuelve a subirlo."
)
AVISO_SIN_SEPARADOR = "no se reconoció un separador de columnas: se leyó como una sola columna"
AVISO_COMILLAS = "el archivo tiene comillas sin cerrar: se leyó sin interpretarlas"

# Una celda más larga que esto se recorta con aviso (research R5): protege el fragmentado y la vectorización de una sola línea
# enorme. Es una protección técnica, no un ajuste de configuración; ningún texto real de una celda se le acerca.
MAX_CELDA_CARACTERES = 20000

# Una secuencia de bytes que es una letra o un signo latino válido en UTF-8 dentro de un archivo en Windows-1252 (celdas pegadas desde
# una página web u otro programa antes de guardar). Se reconoce por la forma de los bytes y se acepta solo si el carácter es una
# letra con tilde, un signo latino o una puntuación común: así un par de símbolos legítimos de Windows-1252 no se toca.
_SECUENCIA_UTF8 = re.compile(rb"[\xc2-\xdf][\x80-\xbf]|[\xe0-\xef][\x80-\xbf]{2}")
_PUNTUACION = set("\u2010\u2011\u2012\u2013\u2014\u2015\u2018\u2019\u201a\u201c\u201d\u201e\u2020\u2021\u2022\u2026\u2030\u2039\u203a\u20ac\u2122")

# Separadores que se reconocen, en orden de preferencia ante un empate: el punto y coma primero porque es lo que exporta Excel en
# español (la coma es el separador decimal). La muestra para decidir son los primeros 64 * 1024 caracteres y 30 registros.
SEPARADORES = (";", ",", "\t", "|")
MUESTRA_CARACTERES = 64 * 1024
MUESTRA_REGISTROS = 30
# Un separador que no aparece nunca en el texto: con él cada fila es una sola columna.
SIN_SEPARADOR = "\x1f"


class CsvLoader(DocumentLoader):
    def load(self, path: Path) -> str:
        self.notes = []
        texto = _decodificar(path.read_bytes())
        if not texto.strip(" \t\r\n\"" + "".join(SEPARADORES)):
            # Solo separadores, comillas y espacios (filas como `;;;`): no hay nada que leer, y sin esta salida un archivo así
            # se leería como una columna de puros separadores.
            raise LoaderError(ERROR_SIN_CONTENIDO)
        avisos: list[str] = []
        separador = _separador(texto)
        if separador is None:
            avisos.append(AVISO_SIN_SEPARADOR)
            separador = SIN_SEPARADOR
        registros, comillas_sin_cerrar = _registros(texto, separador)
        if comillas_sin_cerrar:
            avisos.append(AVISO_COMILLAS)
        recortadas = [0]
        lineas, _, corte, avisos_de_tabla = lineas_de_tabla(
            "", "el archivo", _filas(registros, recortadas), 0, settings.max_excel_rows
        )
        avisos.extend(avisos_de_tabla)
        if not lineas:
            raise LoaderError(ERROR_SIN_CONTENIDO)
        if corte is not None:
            avisos.append(f"el archivo se recortó en la fila {corte} por superar el tope de {settings.max_excel_rows} filas")
        if recortadas[0]:
            n = recortadas[0]
            quien = "se recortó 1 celda que superaba" if n == 1 else f"se recortaron {n} celdas que superaban"
            avisos.append(f"{quien} {MAX_CELDA_CARACTERES} caracteres")
        for detalle in avisos:
            # El aviso también queda en el texto para que una respuesta no presente el archivo como completo (FR-011).
            lineas.append(f"[Aviso: {detalle}]")
            self.notes.append(detalle[0].upper() + detalle[1:] + ".")
        return "\n".join(lineas)


def _decodificar(contenido: bytes) -> str:
    """El texto del archivo, sin que la persona indique la codificación (research R2). En este orden: UTF-16 (por su marca de orden
    de bytes) y los bytes nulos no son un CSV de texto; luego UTF-8 estricto (con o sin marca de orden de bytes), que falla con
    cualquier texto en español guardado como Windows-1252 porque `é` es el byte suelto `E9`; luego Windows-1252 estricto. Si
    ninguna lee el archivo es un error: no se usa latin-1 de respaldo porque aceptaría cualquier cosa y produciría caracteres
    inventados."""
    if contenido.startswith((b"\xff\xfe", b"\xfe\xff")) or b"\x00" in contenido:
        raise LoaderError(ERROR_ILEGIBLE)
    try:
        return contenido.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass
    try:
        return _windows1252_con_celdas_en_utf8(contenido)
    except UnicodeDecodeError:
        raise LoaderError(ERROR_ILEGIBLE) from None


def _windows1252_con_celdas_en_utf8(contenido: bytes) -> str:
    """Windows-1252 estricto, pero las secuencias que son una letra o un signo latino válido en UTF-8 se leen como UTF-8. Pasa en
    archivos reales: casi todo el texto está en Windows-1252 y algunas celdas se pegaron en UTF-8, y leerlos de una sola
    codificación deja `Ã­` en lugar de `í` en esas celdas. Un archivo solo en Windows-1252 no cambia. Lanza `UnicodeDecodeError`
    si algún byte no existe en Windows-1252."""
    partes: list[str] = []
    desde = 0
    for coincidencia in _SECUENCIA_UTF8.finditer(contenido):
        try:
            caracter = coincidencia.group().decode("utf-8")
        except UnicodeDecodeError:
            continue
        if not ("\u00a1" <= caracter <= "\u024f" or caracter in _PUNTUACION):
            continue
        partes.append(contenido[desde : coincidencia.start()].decode("cp1252"))
        partes.append(caracter)
        desde = coincidencia.end()
    partes.append(contenido[desde:].decode("cp1252"))
    return "".join(partes)


def _separador(texto: str) -> str | None:
    """El separador de columnas, o None si no se reconoce ninguno (research R3). Cuenta caracteres no sirve (una coma dentro de un
    texto en un archivo con punto y coma): lo que distingue una tabla es que sus registros tengan la **misma cantidad de campos**.
    Sobre una muestra se lee con cada candidato (respetando las comillas) y el puntaje es la mayor cantidad de registros con un
    mismo número de campos de al menos 2; gana el mayor puntaje y los empates, el orden de `SEPARADORES`."""
    muestra = texto[:MUESTRA_CARACTERES]
    if len(texto) > MUESTRA_CARACTERES:
        corte = max(muestra.rfind("\n"), muestra.rfind("\r")) + 1
        muestra = muestra[:corte] or muestra
    mejor, mejor_puntaje = None, 0
    for candidato in SEPARADORES:
        cuentas: Counter[int] = Counter()
        try:
            for registro in csv.reader(io.StringIO(muestra, newline=""), delimiter=candidato):
                if any(celda.strip() for celda in registro):
                    cuentas[len(registro)] += 1
                if sum(cuentas.values()) >= MUESTRA_REGISTROS:
                    break
        except csv.Error:
            continue
        puntaje = max((veces for campos, veces in cuentas.items() if campos >= 2), default=0)
        if puntaje > mejor_puntaje:
            mejor, mejor_puntaje = candidato, puntaje
    return mejor


def _registros(texto: str, separador: str) -> tuple[list[list[str]], bool]:
    """Los registros del archivo y si hubo comillas sin cerrar (research R4). Se lee con `newline=""` (un archivo con fin de línea
    `\\r` falla sin eso) y de forma **estricta**: ante comillas sin cerrar o mal puestas el módulo lanza `csv.Error` (sin la
    lectura estricta una comilla suelta se traga todo el resto del archivo en una sola celda, sin avisar) y se vuelve a leer sin
    interpretar comillas. El límite de tamaño de campo del módulo se sube solo mientras dura la lectura y se restaura siempre; el
    tope de memoria sigue siendo el tamaño del archivo."""
    limite = csv.field_size_limit()
    csv.field_size_limit(max(limite, len(texto) + 1))
    try:
        try:
            return list(csv.reader(io.StringIO(texto, newline=""), delimiter=separador, strict=True)), False
        except csv.Error:
            sin_comillas = csv.reader(io.StringIO(texto, newline=""), delimiter=separador, quoting=csv.QUOTE_NONE)
            return list(sin_comillas), True
    finally:
        csv.field_size_limit(limite)


def _texto_de_celda(valor: str) -> str | None:
    """El valor tal como está escrito, con los saltos de línea y los espacios repetidos unidos en uno solo (una fila sigue siendo
    una línea); `None` si la celda está vacía. No interpreta números, fechas ni fórmulas (research R6, FR-009 y FR-010)."""
    texto = " ".join(valor.split())
    return texto or None


def _filas(registros, recortadas: list[int]):
    """`(número de registro, textos)` para la lógica compartida. Se numera por registro, no por línea física: una celda con saltos
    de línea ocupa varias líneas del archivo y un solo registro. Las celdas que superan `MAX_CELDA_CARACTERES` se recortan y se
    cuentan en `recortadas[0]`."""
    for numero, campos in enumerate(registros, start=1):
        textos = []
        for campo in campos:
            if len(campo) > MAX_CELDA_CARACTERES:
                campo = campo[:MAX_CELDA_CARACTERES]
                recortadas[0] += 1
            textos.append(_texto_de_celda(campo))
        yield numero, textos
