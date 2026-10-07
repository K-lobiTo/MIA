"""Carga todos los documentos de una o varias carpetas a un dominio de MIA, a través de la API.

Crea el dominio si no existe (lo busca por nombre), sube cada archivo PDF, DOCX o TXT de las
carpetas (recorriendo subcarpetas) y espera a que termine de indexarse antes de subir el
siguiente, para no acumular ingestas en paralelo en la API. Un archivo que ya estaba en el
dominio no se duplica: la API devuelve el documento existente.

Uso (ver "Cargar documentos" en docs/OPERACION.md):
    python scripts/cargar_carpeta.py --url http://localhost:8010 \\
        --dominio "Analítica de Negocios: Consejo de Área" \\
        --descripcion "Actas del Consejo de Área Académica" \\
        "tmp/Información_analítica_de_negocios/ACTAS"

Solo usa la biblioteca estándar, para poder correrlo sin instalar el proyecto.
"""

import argparse
import json
import mimetypes
import sys
import time
import unicodedata
import urllib.error
import urllib.request
import uuid
from pathlib import Path

TIPOS = {".pdf", ".docx", ".txt"}
ESPERA_ESTADO = 5  # segundos entre consultas de estado de un documento en proceso
TIMEOUT = 900  # una tesis larga puede tardar varios minutos en indexarse


def pedir(url: str, metodo: str = "GET", datos: bytes | None = None, tipo: str | None = None):
    request = urllib.request.Request(url, data=datos, method=metodo)
    if tipo:
        request.add_header("Content-Type", tipo)
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return json.loads(response.read())


def obtener_dominio(api: str, nombre: str, descripcion: str) -> str:
    for dominio in pedir(f"{api}/domains"):
        if dominio["name"] == nombre:
            return dominio["id"]
    datos = json.dumps({"name": nombre, "description": descripcion}).encode()
    return pedir(f"{api}/domains", "POST", datos, "application/json")["id"]


def subir(api: str, dominio_id: str, archivo: Path) -> dict:
    # Los nombres pueden venir en Unicode descompuesto (p. ej. al extraer un .zip); se normalizan
    # para que se vean bien en los listados y en las fuentes citadas.
    nombre = unicodedata.normalize("NFC", archivo.name)
    limite = uuid.uuid4().hex
    tipo = mimetypes.guess_type(nombre)[0] or "application/octet-stream"
    cuerpo = (
        f"--{limite}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{nombre}"\r\n'
        f"Content-Type: {tipo}\r\n\r\n"
    ).encode() + archivo.read_bytes() + f"\r\n--{limite}--\r\n".encode()
    url = f"{api}/domains/{dominio_id}/documents"
    return pedir(url, "POST", cuerpo, f"multipart/form-data; boundary={limite}")


def esperar(api: str, dominio_id: str, documento_id: str) -> str:
    while True:
        for documento in pedir(f"{api}/domains/{dominio_id}/documents"):
            if documento["id"] == documento_id and documento["status"] in {"done", "error"}:
                return documento["status"]
        time.sleep(ESPERA_ESTADO)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", required=True, help="URL de la API, con la ingesta activada")
    parser.add_argument("--dominio", required=True, help="Nombre del dominio (se crea si no existe)")
    parser.add_argument("--descripcion", default="", help="Descripción, si se crea el dominio")
    parser.add_argument(
        "--excluir", action="append", default=[], help="Texto en el nombre de archivos a omitir"
    )
    parser.add_argument("carpetas", nargs="+", type=Path)
    args = parser.parse_args()
    api = args.url.rstrip("/")

    archivos = sorted(
        p
        for carpeta in args.carpetas
        for p in carpeta.rglob("*")
        if p.is_file()
        and p.suffix.lower() in TIPOS
        and not any(texto in p.name for texto in args.excluir)
    )
    dominio_id = obtener_dominio(api, args.dominio, args.descripcion)
    print(f"Dominio '{args.dominio}' ({dominio_id}): {len(archivos)} archivos")

    errores = 0
    for i, archivo in enumerate(archivos, 1):
        inicio = time.time()
        try:
            documento = subir(api, dominio_id, archivo)
            estado = documento["status"]
            if estado not in {"done", "error"}:
                estado = esperar(api, dominio_id, documento["id"])
        except urllib.error.URLError as e:
            estado = f"falló la subida ({e})"
        if estado != "done":
            errores += 1
        print(f"[{i}/{len(archivos)}] {estado:6} {time.time() - inicio:6.1f}s  {archivo.name}")
        sys.stdout.flush()

    print(f"Listo: {len(archivos) - errores} indexados, {errores} con error")
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main())
