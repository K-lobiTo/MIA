#!/usr/bin/env python3
"""Envía al bot un aviso de Kapso firmado, como el que llegaría cuando una persona escribe por WhatsApp.

Uso:
    python whatsapp/scripts/enviar_webhook.py --secreto SECRETO --numero 111 "¿Cuándo es la matrícula?"
    python whatsapp/scripts/enviar_webhook.py --secreto SECRETO --numero 111 --id wamid.1 "hola"   # el mismo --id: duplicado
    python whatsapp/scripts/enviar_webhook.py --secreto SECRETO --numero 111 --tipo audio          # no es texto
    python whatsapp/scripts/enviar_webhook.py --secreto SECRETO --numero 111 --persona ana "hola"  # otra persona
    python whatsapp/scripts/enviar_webhook.py --secreto SECRETO --numero 111 --sin-telefono "hola" # sin teléfono (BSUID)
    python whatsapp/scripts/enviar_webhook.py --secreto equivocado --numero 111 "hola"             # 401: firma inválida

`--numero` es el phone_number_id de Kapso del bot (el del panel). El secreto es el mismo KAPSO_WEBHOOK_SECRET del bot (o la
variable de entorno del mismo nombre). Solo usa la biblioteca estándar.
"""

import argparse
import hashlib
import hmac
import json
import os
import sys
import urllib.error
import urllib.request
import uuid

EVENTO = "whatsapp.message.received"


def firmar(cuerpo: bytes, secreto: str) -> str:
    """La firma de Kapso: HMAC-SHA256 del cuerpo crudo con el secreto, en hexadecimal minúscula y sin prefijo."""
    return hmac.new(secreto.encode(), cuerpo, hashlib.sha256).hexdigest()


def datos_de_persona(persona: str) -> tuple[str, str]:
    """Un teléfono y un identificador de usuario de mentira, siempre los mismos para la misma persona."""
    digitos = str(int(hashlib.sha256(persona.encode()).hexdigest(), 16))[:8]
    return f"506{digitos}", f"US.{digitos}00000"


def armar_aviso(
    texto: str | None,
    numero: str,
    mensaje_id: str,
    persona: str = "persona-1",
    tipo: str = "text",
    sin_telefono: bool = False,
) -> dict:
    """El aviso `whatsapp.message.received` con la forma de la documentación de Kapso. Con `sin_telefono` no trae `from`
    ni `conversation.phone_number` (como cuando Kapso solo entrega el identificador de usuario)."""
    telefono, usuario = datos_de_persona(persona)
    mensaje: dict = {"id": mensaje_id, "timestamp": "1730092800", "type": tipo, "from_user_id": usuario}
    conversacion: dict = {"id": f"conv_{persona}", "phone_number_id": numero}
    if not sin_telefono:
        mensaje["from"] = telefono
        conversacion["phone_number"] = telefono
    if tipo == "text":
        mensaje["text"] = {"body": texto or ""}
    return {"message": mensaje, "conversation": conversacion, "is_new_conversation": False, "phone_number_id": numero}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("texto", nargs="?", default="", help="la pregunta (vacía si --tipo no es text)")
    parser.add_argument("--url", default="http://localhost:8100/webhooks/kapso")
    parser.add_argument("--secreto", default=os.environ.get("KAPSO_WEBHOOK_SECRET", ""))
    parser.add_argument("--numero", required=True, help="el phone_number_id de Kapso del bot")
    parser.add_argument("--id", dest="mensaje_id", help="id del mensaje (por defecto uno nuevo); repetirlo prueba el duplicado")
    parser.add_argument("--persona", default="persona-1", help="quién escribe: la misma persona repite su teléfono")
    parser.add_argument("--tipo", default="text", help="text, audio, image, sticker...")
    parser.add_argument("--sin-telefono", action="store_true", help="el aviso no trae teléfono, solo identificador de usuario")
    parser.add_argument("--firma-mala", action="store_true", help="firmar con un secreto equivocado (el bot debe responder 401)")
    parser.add_argument("--evento", default=EVENTO, help="encabezado X-Webhook-Event")
    args = parser.parse_args(argv)

    if not args.secreto:
        print("Falta el secreto: --secreto o la variable KAPSO_WEBHOOK_SECRET.", file=sys.stderr)
        return 2
    mensaje_id = args.mensaje_id or f"wamid.local.{uuid.uuid4().hex[:8]}"
    aviso = armar_aviso(args.texto, args.numero, mensaje_id, args.persona, args.tipo, args.sin_telefono)
    cuerpo = json.dumps(aviso, ensure_ascii=False).encode()
    firma = firmar(cuerpo, "firma-equivocada" if args.firma_mala else args.secreto)
    peticion = urllib.request.Request(
        args.url,
        data=cuerpo,
        method="POST",
        headers={
            "content-type": "application/json",
            "x-webhook-event": args.evento,
            "x-webhook-signature": firma,
            "x-idempotency-key": f"k-{mensaje_id}",
        },
    )
    try:
        with urllib.request.urlopen(peticion, timeout=15) as respuesta:
            print(f"{respuesta.status} {respuesta.read().decode()}  (id del mensaje: {mensaje_id})")
    except urllib.error.HTTPError as error:
        print(f"{error.code} {error.read().decode()}  (id del mensaje: {mensaje_id})")
        return 1
    except urllib.error.URLError as error:
        print(f"No se pudo conectar con {args.url}: {error.reason}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
