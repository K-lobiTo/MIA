"""SOLO DESARROLLO: captura lo que el servicio real del bot de WhatsApp envía, para el video D1.

Levanta un Kapso falso (recibe lo que el bot enviaría) y el servicio `mia_whatsapp` apuntando a la API de demostración
(`servidor_demo.py` debe estar corriendo), le manda avisos firmados como los de Kapso y guarda en
`datos_demo/whatsapp.json` los mensajes de cada escenario. Así el chat del video usa los textos reales del servicio
(saludo, formato, fuentes, aclaración, límites) y no unos inventados.

    python scripts/demos/capturar_whatsapp.py
"""

import json
import subprocess
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "whatsapp" / "scripts"))
import enviar_webhook as webhook

SALIDA = Path(__file__).resolve().parent / "datos_demo" / "whatsapp.json"
NUMERO = "demo-phone-number-id"  # el bot sembrado por servidor_demo.py
SECRETO = "secreto-demo"
PUERTO_KAPSO, PUERTO_BOT = 9100, 8100

enviados: list[dict] = []


class KapsoFalso(BaseHTTPRequestHandler):
    def do_POST(self):
        cuerpo = json.loads(self.rfile.read(int(self.headers.get("content-length") or 0)) or b"{}")
        enviados.append(cuerpo)
        datos = json.dumps({"messages": [{"id": f"wamid.demo.{len(enviados)}"}]}).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def log_message(self, *args):
        pass


def enviar(texto: str | None, persona: str, tipo: str = "text") -> list[dict]:
    """Manda un aviso firmado al bot y devuelve los mensajes que respondió (texto o imagen), en orden."""
    antes = len(enviados)
    id_ = f"wamid.demo.{time.monotonic_ns()}"
    cuerpo = json.dumps(webhook.armar_aviso(texto, NUMERO, id_, persona, tipo), ensure_ascii=False).encode()
    peticion = urllib.request.Request(
        f"http://localhost:{PUERTO_BOT}/webhooks/kapso",
        data=cuerpo,
        method="POST",
        headers={
            "content-type": "application/json",
            "x-webhook-event": webhook.EVENTO,
            "x-webhook-signature": webhook.firmar(cuerpo, SECRETO),
            "x-idempotency-key": f"k-{id_}",
        },
    )
    urllib.request.urlopen(peticion, timeout=15).read()
    # Se espera a que el bot termine: nada nuevo durante 2 segundos.
    ultimo, cambio = len(enviados), time.monotonic()
    while time.monotonic() - cambio < 2.0:
        time.sleep(0.2)
        if len(enviados) != ultimo:
            ultimo, cambio = len(enviados), time.monotonic()
    return [_simple(m) for m in enviados[antes:]]


def _simple(cuerpo: dict) -> dict:
    if cuerpo.get("type") == "image":
        imagen = cuerpo["image"]
        return {"tipo": "imagen", "enlace": imagen.get("link", ""), "pie": imagen.get("caption", "")}
    return {"tipo": "texto", "texto": cuerpo.get("text", {}).get("body", "")}


def main() -> int:
    servidor = ThreadingHTTPServer(("127.0.0.1", PUERTO_KAPSO), KapsoFalso)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    entorno = {
        "MIA_API_URL": "http://localhost:8000",
        "BOT_SERVICE_KEY": "clave-servicio-demo",
        "KAPSO_API_KEY": "clave-kapso-demo",
        "KAPSO_WEBHOOK_SECRET": SECRETO,
        "KAPSO_API_URL": f"http://localhost:{PUERTO_KAPSO}",
        "PATH": "/usr/bin:/bin",
    }
    bot = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "mia_whatsapp.main:create_app", "--factory", "--port", str(PUERTO_BOT), "--log-level", "warning"],
        env=entorno,
        cwd=RAIZ / "whatsapp",
    )
    try:
        for _ in range(50):  # espera a que el servicio responda
            try:
                urllib.request.urlopen(f"http://localhost:{PUERTO_BOT}/health", timeout=1).read()
                break
            except OSError:
                time.sleep(0.3)
        escenarios = []

        def agregar(id_: str, titulo: str, persona: str, entrada: str, mensajes: list[dict]) -> None:
            escenarios.append({"id": id_, "titulo": titulo, "persona": persona, "entrada": entrada, "mensajes": mensajes})
            print(f"{id_}: {len(mensajes)} mensajes")

        # Una sola persona, en el orden de la historia del video: el saludo va en su primera respuesta y, mientras no haya un
        # programa recordado, la pregunta ambigua se aclara.
        persona = "ana"
        ambigua = "¿Cuánto cuesta la matrícula?"
        agregar("aclaracion-pregunta", "Pregunta ambigua entre programas", persona, ambigua, enviar(ambigua, persona))
        agregar("aclaracion-respuesta", "La persona elige el programa", persona, "Computación", enviar("Computación", persona))
        pregunta = "¿Cuántos créditos tiene el Taller de Ejemplo A?"
        agregar("respuesta", "Una pregunta con respuesta e imagen", persona, pregunta, enviar(pregunta, persona))
        fuera = "¿Cuál es el menú de la cafetería?"
        agregar("sin-informacion", "La pregunta no está en los documentos", persona, fuera, enviar(fuera, persona))
        agregar("no-texto", "Un audio", persona, "(audio)", enviar(None, persona, tipo="audio"))
        for n in range(1, 16):  # mensajes seguidos hasta que el bot avise el límite por hora
            mensajes = enviar(f"hola {n}", persona)
            if mensajes and "muchos mensajes" in mensajes[-1].get("texto", ""):
                agregar("limite", "Demasiados mensajes seguidos", persona, f"hola {n}", mensajes)
                break
        SALIDA.write_text(json.dumps({"numero": NUMERO, "escenarios": escenarios}, ensure_ascii=False, indent=2), encoding="utf-8")
        print("guardado", SALIDA)
    finally:
        bot.terminate()
        servidor.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
