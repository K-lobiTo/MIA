# Quickstart: validar los datos de contacto de WhatsApp

Guía para comprobar la feature de punta a punta. Los detalles de las rutas están en los [contratos](contracts/) y los de la tabla en [data-model.md](data-model.md). No lleva código de implementación.

## Prerrequisitos

```bash
source .venv/bin/activate
pip install -e ".[dev]" && pip install -e "./whatsapp[dev]"
cp .env.example .env        # BOT_SERVICE_KEY con un valor; en el servicio, BOT_CONTACT=on para esta guía
docker compose up -d qdrant
cd web/admin && npm install && cd ../..
```

Migración: la API migra la base al arrancar (`0012` crea `whatsapp_contacts`). Para comprobarlo sin arrancar: `alembic upgrade head` con `DATABASE_URL`.

## 1. Pruebas automáticas

```bash
pytest tests/unit/test_contacts_store.py tests/unit/test_contacts_service_api.py \
       tests/unit/test_contacts_admin_api.py tests/unit/test_contacts_privacidad.py \
       tests/unit/test_migrations.py tests/unit/test_bot_end_to_end.py
pytest whatsapp/tests/test_contacts_rules.py whatsapp/tests/test_flow_contacts.py
pytest                                    # toda la suite: nada de la 011 a la 016 debe cambiar
ruff check src tests scripts whatsapp
cd web/admin && npm test && npm run build
```

Resultado esperado: todo en verde. Con `BOT_CONTACT=off` (el defecto) las pruebas existentes de la 011 pasan **sin cambios** (SC-007).

## 2. Recorrido con los simuladores locales (sin Kapso ni cuota)

Terminal 1: la API (`uvicorn mia.api.main:app --reload`). Terminal 2: el servicio con `BOT_CONTACT=on` apuntando al simulador de Kapso (`whatsapp/scripts/kapso_falso.py`). Se envían avisos con `whatsapp/scripts/enviar_webhook.py`.

| Paso | Qué se hace | Qué se debe ver |
|---|---|---|
| 1 | Un teléfono nuevo escribe una pregunta | El simulador recibe **dos** mensajes: la respuesta (con el saludo) y, aparte, la invitación (dice "opcional" y qué se guarda). La base tiene un contacto `invitada`. |
| 2 | Responde `Ana Pérez ana@correo.com` | Un mensaje de confirmación con el correo enmascarado. Contacto `entrego` con nombre y correo. No hay llamada a `/bot/query` para ese mensaje. |
| 3 | Escribe otra pregunta | Se responde normal, sin invitación. |
| 4 | Otro teléfono nuevo: pregunta y luego responde `no` | Confirmación breve; contacto `declino` sin nombre ni correo. Una pregunta posterior no vuelve a invitar. |
| 5 | Otro teléfono nuevo: pregunta y luego otra pregunta (ignora la invitación) | La segunda pregunta se responde normal y el contacto queda `declino`. |
| 6 | Un teléfono con datos escribe `borrar mis datos` | Confirmación; el contacto queda `declino` sin nombre ni correo. |
| 7 | Reintento del mismo aviso (misma clave de idempotencia) y dos mensajes simultáneos de un teléfono nuevo | Un solo contacto y **una sola** invitación. |
| 8 | Se detiene la API y llega un mensaje | El bot responde como siempre o con "no disponible" (como hoy); no se rompe y el log no trae teléfonos. |
| 9 | `BOT_CONTACT=off` y se repite el paso 1 | Un solo mensaje (la respuesta), sin invitación y sin filas nuevas. |

## 3. Privacidad (SC-005)

```bash
# Ningún teléfono, nombre o correo de prueba en Uso ni en los registros
sqlite3 mia.db "select count(*) from queries where question like '%ana@correo.com%' or question like '%Ana P%';"   # 0
grep -c "88887777\|ana@correo.com" <(logs del servicio y de la API)                                               # 0
sqlite3 mia.db "select phone, name, email, status from whatsapp_contacts;"                                        # solo lo esperado
```

## 4. Panel (alcance global)

```bash
cd web/admin && npm run dev
```

1. Con una cuenta **global**: abrir "Contactos de WhatsApp", ver la lista y los totales por estado, filtrar por estado y "con correo".
2. **Descargar CSV**: abrirlo en una hoja de cálculo: acentos correctos, una fila por contacto, y un nombre de prueba como `=1+1` aparece como texto (con apóstrofo), no como fórmula.
3. **Borrar** un contacto: la ventana advierte que no se puede deshacer; desaparece de la lista y de la base; el contacto vuelve a ser "nuevo" si ese teléfono escribe otra vez.
4. **Borrar los filtrados**: la ventana muestra el conteo; si entre tanto cambia el conteo, la API responde 409 y no borra.
5. Con una cuenta **de programa**: el módulo no aparece y `GET /contacts` responde 403.
6. En el registro de administración (salida de la API) hay una línea por descarga y por borrado, **sin** teléfonos, nombres ni correos.

## 5. Con el sandbox de Kapso (aceptación)

Desde un teléfono registrado como de prueba: repetir los pasos 1, 2, 4 y 6. Comprobar en Kapso que los mensajes de invitación llegan **después** de la respuesta y que la cuota del mes sube en la cantidad esperada (la invitación cuenta 1 mensaje enviado por persona nueva).

## 6. Cómo volver atrás

- Apagar la función: `BOT_CONTACT=off` en el servicio (los datos guardados se conservan).
- Quitar los datos: borrar desde el panel (o la base) y, si hace falta, `alembic downgrade 0011` (**borra la tabla**: descargar el CSV antes). Una API anterior a la `0012` no arranca sobre una base que la aplicó.
