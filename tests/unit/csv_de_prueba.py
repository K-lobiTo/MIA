"""CSV inventados para las pruebas de la feature 021 (ingesta de CSV). **Ningún dato es real**: los nombres son `Persona NN`,
los correos terminan en `@ejemplo.test` y las cédulas y los celulares son solo ceros. Reproducen la **estructura** y los problemas
de un CSV exportado de Excel en español (Windows-1252, punto y coma, celdas con saltos de línea, filas vacías, una última
columna sin nombre) sin copiar nada de ningún archivo real. No se guardan archivos en el repositorio: se arman en memoria.

Para escribir el CSV de ejemplo en una ruta (lo usa el quickstart): `python tests/unit/csv_de_prueba.py /tmp/ejemplo.csv`."""

import csv
import io
import sys

ENCABEZADOS_COMO_EL_REAL = [
    "N°", "Nombre", "Cédula", "Correo", "Celular", "Dirección", "Título", "Universidad", "Grado", "Certificados",
    "Promedio de cursos", "Puntaje de cursos", "Formación profesional", "Experiencia en analítica",
    "Formación complementaria", "Carta motivacional", "Prom. P", "Visualización", "SQL", "Python o R", "Programación",
    "ML y Big Data", "Certificación o técnico", "Experiencia relacionada", "Labores", "Puesto", "Confirma", "Pago", "",
]


def csv_bytes(
    registros: list[list[str]],
    *,
    separador: str = ";",
    codificacion: str = "cp1252",
    bom: bool = False,
    fin_de_linea: str = "\r\n",
) -> bytes:
    """Los bytes de un CSV con esos registros. `codificacion`: `utf-8`, `cp1252` o `utf-16` (con su marca de orden de bytes);
    `bom` agrega la marca de UTF-8. Las celdas con el separador, comillas o saltos de línea se entrecomillan solas."""
    salida = io.StringIO(newline="")
    escritor = csv.writer(salida, delimiter=separador, lineterminator=fin_de_linea)
    escritor.writerows(registros)
    contenido = salida.getvalue().encode(codificacion)
    return (b"\xef\xbb\xbf" + contenido) if bom else contenido


def tabla_inventada(filas: int = 3) -> list[list[str]]:
    """Encabezados con tildes y `filas` filas de datos inventados (curso, créditos, profesor, correo)."""
    registros = [["Código", "Nombre del curso", "Créditos", "Profesor", "Correo"]]
    for i in range(1, filas + 1):
        registros.append([f"MC{4000 + i}", f"Curso número {i} (Ñandú)", str(3 + i % 2), f"Persona {i:02d}", correo(i)])
    return registros


def correo(numero: int) -> str:
    return f"correo{numero:02d}@ejemplo.test"


def csv_como_el_real() -> bytes:
    """Reproduce la estructura de un CSV real de Excel en español: 29 columnas con la última sin nombre, 45 registros (el
    encabezado, 41 filas de datos y 3 filas vacías), 11 celdas con saltos de línea, Windows-1252, punto y coma y fin de línea
    de Windows. Varias filas traen un valor en la última columna, la que no tiene encabezado."""
    registros: list[list[str]] = [list(ENCABEZADOS_COMO_EL_REAL)]
    vacias = {9, 21, 33}  # posiciones (dentro de los datos) de las 3 filas vacías
    multilinea = 0
    for i in range(1, 45):
        if i in vacias:
            registros.append([""] * 29)
            continue
        fila = [""] * 29
        fila[0] = str(i)
        fila[1] = f"Persona {i:02d}"
        fila[2] = "0-0000-0000"
        fila[3] = correo(i)
        fila[4] = "0000-0000"
        fila[5] = f"Barrio Ejemplo, casa {i}"
        fila[6] = "Ingeniería en Computación"
        fila[7] = "Universidad de Ejemplo"
        fila[10] = f"{80 + i % 20}"
        fila[15] = "Me interesa la maestría por su enfoque en analítica"
        if multilinea < 11 and i % 4 == 0:
            fila[24] = "Primera labor\nSegunda labor\nTercera labor"
            multilinea += 1
        else:
            fila[24] = "Análisis de datos"
        fila[26] = "Sí" if i % 2 else "No"
        if i % 5 == 0:
            fila[28] = f"Nota {i}"  # valor en la columna final, sin encabezado
        registros.append(fila)
    assert multilinea == 11, "el generador debe producir 11 celdas con saltos de línea"
    return csv_bytes(registros)


def csv_con_codificaciones_mezcladas() -> bytes:
    """Un CSV en Windows-1252 donde algunas celdas están en UTF-8 (lo que pasa al copiar y pegar texto desde una página web o
    desde otro programa antes de guardar el archivo): la mayoría de las celdas con `é` como el byte `E9` y otras con `é` como
    los dos bytes `C3 A9`. Ni UTF-8 ni Windows-1252 por separado lo leen bien."""
    filas = [
        ("Código", "Título", "Descripción"),
        ("A1", "Ingeniería en Computación", "Cañón de datos"),  # Título en UTF-8, Descripción en Windows-1252
        ("A2", "Administración", "Número de teléfono"),  # Título en Windows-1252, Descripción en UTF-8
        ("A3", "Gestión pública", "Año 2026 «completo» – “ok” €"),  # UTF-8 con comillas, guion largo y euro
    ]
    en_utf8 = {("A1", 1), ("A2", 2), ("A3", 1), ("A3", 2)}
    salida = bytearray()
    for fila in filas:
        celdas = []
        for indice, texto in enumerate(fila):
            codificacion = "utf-8" if (fila[0], indice) in en_utf8 else "cp1252"
            celdas.append(texto.encode(codificacion))
        salida += b";".join(celdas) + b"\r\n"
    return bytes(salida)


def csv_con_comilla_sin_cerrar() -> bytes:
    """Un CSV UTF-8 con una comilla que nunca se cierra a mitad del archivo (R4)."""
    texto = 'Código;Nombre\r\nA1;Ana\r\nA2;"Beto sin cerrar\r\nA3;Carla\r\nA4;Diego\r\n'
    return texto.encode("utf-8")


def csv_con_celda_de(caracteres: int, *, separador: str = ";") -> bytes:
    """Un CSV UTF-8 con una celda del largo dado (para los topes de celda y de memoria)."""
    return csv_bytes(
        [["Código", "Texto"], ["A1", "x" * caracteres], ["A2", "corta"]], separador=separador, codificacion="utf-8"
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Uso: python tests/unit/csv_de_prueba.py <ruta del CSV a escribir>")
    with open(sys.argv[1], "wb") as destino:
        destino.write(csv_como_el_real())
    print(f"CSV de ejemplo escrito en {sys.argv[1]}")
