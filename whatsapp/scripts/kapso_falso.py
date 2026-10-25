#!/usr/bin/env python3
"""Kapso falso: imita la API de envío de WhatsApp de Kapso para probar el bot en la laptop sin gastar cuota.

Recibe `POST /{phone_number_id}/messages` (lo que el bot envía), imprime en la consola cada texto o imagen y responde
200 con un cuerpo de éxito. Es local: imprime el contenido completo, sin ocultar nada.

Uso:
    python whatsapp/scripts/kapso_falso.py --puerto 9000
    python whatsapp/scripts/kapso_falso.py --puerto 9000 --fallar-imagenes   # rechaza las imágenes con un 400

y el bot se apunta a él con KAPSO_API_URL=http://localhost:9000.
Solo usa la biblioteca estándar.
"""

import argparse
import itertools
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_contador = itertools.count(1)
_RUTA = re.compile(r"^/(?P<numero>[^/]+)/messages/?$")


def describir(numero: str, cuerpo: dict) -> str:
    """Una línea legible de lo que el bot envió."""
    destino = cuerpo.get("to") or cuerpo.get("recipient") or "(sin destino)"
    tipo = cuerpo.get("type")
    if tipo == "text":
        return f"[TEXTO a {destino} desde {numero}]\n{cuerpo.get('text', {}).get('body', '')}"
    if tipo == "image":
        imagen = cuerpo.get("image", {})
        return f"[IMAGEN a {destino} desde {numero}] {imagen.get('link', '')} | pie de foto: {imagen.get('caption', '(sin pie)')}"
    return f"[{tipo} a {destino} desde {numero}] {json.dumps(cuerpo, ensure_ascii=False)}"


def responder(ruta: str, cuerpo_crudo: bytes, fallar_imagenes: bool = False) -> tuple[int, dict, str | None]:
    """El estado HTTP, el cuerpo y la línea a imprimir para una petición. No abre ningún puerto: es lo que prueban las pruebas."""
    coincide = _RUTA.match(ruta)
    if not coincide:
        return 404, {"error": {"message": "ruta desconocida"}}, None
    try:
        cuerpo = json.loads(cuerpo_crudo.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return 400, {"error": {"message": "cuerpo ilegible"}}, None
    linea = describir(coincide.group("numero"), cuerpo)
    if fallar_imagenes and cuerpo.get("type") == "image":
        return 400, {"error": {"message": "imagen rechazada (simulado con --fallar-imagenes)"}}, linea + "  <- RECHAZADA"
    return 200, {"messages": [{"id": f"wamid.falso.{next(_contador)}"}]}, linea


def crear_servidor(puerto: int, fallar_imagenes: bool = False) -> ThreadingHTTPServer:
    class Manejador(BaseHTTPRequestHandler):
        def do_POST(self):
            largo = int(self.headers.get("content-length") or 0)
            estado, cuerpo, linea = responder(self.path, self.rfile.read(largo), fallar_imagenes)
            if linea:
                print(linea, flush=True)
            datos = json.dumps(cuerpo).encode()
            self.send_response(estado)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(datos)))
            self.end_headers()
            self.wfile.write(datos)

        def log_message(self, *args):  # sin el registro de cada petición: ya se imprime lo que importa
            pass

    return ThreadingHTTPServer(("127.0.0.1", puerto), Manejador)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--puerto", type=int, default=9000)
    parser.add_argument("--fallar-imagenes", action="store_true", help="rechazar las imágenes con un 400 (prueba de imagen_fallida)")
    args = parser.parse_args()
    servidor = crear_servidor(args.puerto, args.fallar_imagenes)
    print(f"Kapso falso escuchando en http://127.0.0.1:{args.puerto} (Ctrl+C para salir)", flush=True)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
