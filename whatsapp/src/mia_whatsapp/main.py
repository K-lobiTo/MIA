"""La aplicación del servicio: GET /health y POST /webhooks/kapso.

Se arranca con `uvicorn mia_whatsapp.main:create_app --factory`: la configuración se lee al crear la aplicación y no al
importar el módulo (así las pruebas importan sin variables de entorno). El aviso de Kapso se confirma con 200 apenas la
firma y el cuerpo son válidos; el mensaje se procesa después, en una tarea de fondo, porque Kapso exige 200 en menos de
10 segundos y reintenta si no llega. Ver specs/011-bot-whatsapp-kapso/contracts/servicio-whatsapp.md.
"""

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import JSONResponse

from mia_whatsapp.api_client import MiaApiClient
from mia_whatsapp.config import Settings, contact_warnings, get_settings
from mia_whatsapp.flow import Deps, handle_message
from mia_whatsapp.kapso import KapsoClient
from mia_whatsapp.logs import log_result
from mia_whatsapp.state import State
from mia_whatsapp.webhook import IncomingMessage, parse_event, verify_signature

logger = logging.getLogger("mia_whatsapp")

# Cada cuánto se retira del estado en memoria lo vencido.
CLEANUP_INTERVAL_S = 60

Handler = Callable[[IncomingMessage, Deps], Awaitable[None]]


async def _cleanup_loop(state: State) -> None:
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL_S)
        state.cleanup()


def create_app(
    settings: Settings | None = None,
    api: MiaApiClient | None = None,
    kapso: KapsoClient | None = None,
    handler: Handler | None = None,
) -> FastAPI:
    """Los clientes y el manejador se pueden inyectar (las pruebas los sustituyen); por defecto son los reales."""
    settings = settings or get_settings()
    api = api or MiaApiClient(settings)
    kapso = kapso or KapsoClient(settings)
    deps = Deps(settings=settings, state=State(settings), api=api, kapso=kapso)
    process = handler or handle_message

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # El bot no da el contacto del programa: si un texto cambiado por variable lo trae, se avisa (sin impedir arrancar).
        for name in contact_warnings(settings):
            logger.warning("%s parece traer un contacto (correo, enlace o teléfono): el bot no debe dar el contacto", name)
        cleanup = asyncio.create_task(_cleanup_loop(deps.state))
        try:
            yield
        finally:
            cleanup.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await cleanup
            await api.aclose()
            await kapso.aclose()

    app = FastAPI(title="MIA: bot de WhatsApp", lifespan=lifespan)
    app.state.deps = deps

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.post("/webhooks/kapso")
    async def kapso_webhook(request: Request, background: BackgroundTasks):
        # La firma es del cuerpo crudo: se lee antes de interpretar nada.
        body = await request.body()
        if not verify_signature(body, request.headers.get("x-webhook-signature"), settings.kapso_webhook_secret):
            return JSONResponse({"detail": "Firma inválida."}, status_code=401)
        parsed = parse_event(request.headers, body)
        if parsed.unreadable:
            # Con firma válida pero ilegible no se pide reintento (no se podrá leer mejor): se registra y se confirma.
            log_result("cuerpo_ilegible", 0)
        for message in parsed.messages:
            background.add_task(process, message, deps)
        return {"status": "ok"}

    return app
