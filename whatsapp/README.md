# mia-whatsapp: servicio del bot de WhatsApp

Recibe los avisos firmados de [Kapso](https://docs.kapso.ai), consulta a la API de MIA con el artefacto asignado al bot (siempre en modo literal) y responde por WhatsApp con el texto y, si el documento tiene imágenes asociadas, con la imagen. Un solo servicio atiende todos los números de WhatsApp: el bot se resuelve por el `phone_number_id` de cada aviso.

No importa el paquete `mia`: habla con la API solo por HTTP. Diseño y contratos en [`specs/011-bot-whatsapp-kapso/`](../specs/011-bot-whatsapp-kapso/) (en especial [`contracts/servicio-whatsapp.md`](../specs/011-bot-whatsapp-kapso/contracts/servicio-whatsapp.md)).

Primera entrega: solo el sandbox de Kapso. El camino a producción está en la sección 11 de [`docs/Definicion_Requerimientos_Bot_WhatsApp.md`](../docs/Definicion_Requerimientos_Bot_WhatsApp.md).

## Desarrollo

```bash
pip install -e "./whatsapp[dev]"       # desde la raíz del repositorio
cd whatsapp && pytest                  # o `pytest whatsapp/tests` desde la raíz
ruff check whatsapp
```

Las variables están en [`.env.example`](.env.example).

## Cómo se prueba y se corre

- **Pruebas** (`whatsapp/tests/`): el receptor, el flujo y los clientes con `httpx.MockTransport` y la API de MIA y Kapso simuladas, sin red. El `TestClient` de FastAPI ejecuta las tareas de fondo antes de devolver, así que no demuestra que el 200 sale antes de procesar: `tests/test_app.py` lo prueba llamando a la aplicación ASGI a mano. Las ayudas (firma, avisos de ejemplo y servicios simulados) están en `tests/support.py`; la carpeta `tests/` **no** lleva `__init__.py` para no chocar con el paquete `tests` de la API cuando el `pytest` de la raíz corre las dos.
- **Arrancar en local**: la aplicación se crea con una fábrica y lee su configuración al arrancar:

  ```bash
  cd whatsapp
  MIA_API_URL=http://localhost:8000 BOT_SERVICE_KEY=clave-local KAPSO_API_KEY=x \
    KAPSO_WEBHOOK_SECRET=secreto KAPSO_API_URL=http://localhost:9000 \
    uvicorn mia_whatsapp.main:create_app --factory --port 8100
  ```

  La API local debe tener la misma `BOT_SERVICE_KEY` (y `QUERY_CITED_SOURCES=on` para las imágenes). Sin una variable obligatoria el servicio no arranca y el mensaje nombra la variable.
- **Contexto y aclaración (feature 013).** **Cuánto recuerda lo fija la memoria del bot (feature 014):** se ajusta desde el módulo Bots del panel, en vueltas (una pregunta y su respuesta, de 1 a 10, por defecto 2), la API la informa en cada `POST /bot/messages` (`context_turns`) y el servicio mira los últimos `2 * context_turns` turnos (un turno es un mensaje), con efecto desde el mensaje siguiente y sin reiniciar; `BOT_CONTEXT_MESSAGES` solo rige si la API no informa el valor. El bot no le entrega la conversación al modelo. El servicio recuerda en memoria los turnos de cada persona (hasta 20 guardados) (por su clave con hash, nunca el teléfono), durante `BOT_CONTEXT_MINUTES` (30) de inactividad y con un tope de `BOT_CONTEXT_MAX_PEOPLE` (5.000) conversaciones; se pierde al reiniciar. Sirve para que, cuando la API devuelve programas candidatos (la pregunta no nombra el programa y varios tienen la respuesta), el bot pregunte con `BOT_TEXT_CLARIFY` (`{programs}` = lista numerada) y resuelva la respuesta de la persona, y para reintentar una vez con el programa de la conversación. La API decide la ambigüedad con `BOT_CLARIFY=on`.
- **Simuladores** (`whatsapp/scripts/`, solo biblioteca estándar): `kapso_falso.py --puerto 9000` imita la API de envío de Kapso e imprime lo que el bot enviaría (con `--fallar-imagenes` rechaza las imágenes), y `enviar_webhook.py --secreto secreto --numero <phone_number_id> "pregunta"` envía un aviso firmado (`--id` repetido prueba el duplicado, `--tipo audio`, `--persona`, `--sin-telefono`, `--firma-mala`). Recorrido completo en el [quickstart](../specs/011-bot-whatsapp-kapso/quickstart.md).
- **Imagen de Docker**: `docker build whatsapp/` (unos 170 MB). Se despliega en Railway con *Root Directory* `whatsapp`; ver [docs/OPERACION.md](../docs/OPERACION.md#el-bot-de-whatsapp-feature-011).

## Cómo está organizado

| Archivo | Para qué |
|---|---|
| `main.py` | La aplicación (`create_app`): `GET /health`, `POST /webhooks/kapso` (firma, 200 inmediato, procesa en una tarea de fondo) y la limpieza periódica del estado |
| `webhook.py` | Firma HMAC-SHA256 del cuerpo crudo, lectura del aviso (también en lote), destino de la respuesta sin dar por seguro el teléfono |
| `flow.py` | El orden de las decisiones por mensaje: duplicado, cuenta, tope mensual, límite por persona, estado del bot, tipo, largo, cola y consulta |
| `state.py` | Memoria acotada: mensajes ya vistos, saludo, ventanas por persona y cola de consultas |
| `api_client.py` | `POST /bot/messages` y `POST /bot/query` con la credencial de servicio |
| `kapso.py` | Envío de texto e imagen, limitador por minuto y un reintento |
| `format.py` | De Markdown al formato de WhatsApp, fuentes breves y partición en mensajes |
| `logs.py` | Una línea JSON por mensaje, sin teléfonos ni textos |
| `config.py` | Variables, rangos, textos fijos y el resguardo de que ningún texto traiga un contacto |
