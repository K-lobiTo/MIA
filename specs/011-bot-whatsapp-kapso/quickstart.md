# Quickstart: validar el bot de WhatsApp

Guía para comprobar la feature de punta a punta, de lo más barato (pruebas automáticas y simulador) al sandbox de Kapso, que es el único entorno real de esta entrega (la producción queda documentada, no se hace). Detalles de diseño en [research.md](research.md), [data-model.md](data-model.md) y [contracts/](contracts/). Todo el desarrollo se hace en `dev`; el despliegue sale de `origin/main` (paso 6).

## 0. Prerrequisitos

```bash
source .venv/bin/activate && pip install -e ".[dev]" && pip install -e "./whatsapp[dev]"
docker compose up -d qdrant           # Qdrant local
cd web/admin && npm ci && cd ../..    # solo si se prueba el panel
```

## 1. Pruebas automáticas (sin red, sin Kapso y sin cuota)

```bash
pytest tests/unit/test_bots.py tests/unit/test_bot_service.py tests/unit/test_images.py tests/unit/test_query_images.py
pytest tests/unit/test_migrations.py tests/unit/test_config.py tests/unit/test_servicios.py tests/unit/test_probar_migracion.py
pytest whatsapp/tests                      # el receptor con Kapso y la API simulados
pytest && ruff check src tests scripts bot
cd web/admin && npm run typecheck && npm test && npm run build
```

Lo que deben demostrar:
- **API**: bots (registro, cambio de artefacto, activar y desactivar, alcance global, auditoría), la credencial de servicio, el contador mensual (atómico, mes nuevo en cero, `cap_reached`), `POST /bot/query` (artefacto asignado, modo literal fijo, dominios del artefacto, rechazos, registro en Uso sin teléfono) y que un cambio de artefacto o de dominios rige en la consulta siguiente.
- **Imágenes**: formato por contenido, tamaño, final del archivo, alcance, orden, reemplazo con enlace nuevo, `/media` pública, y el campo `images` de la consulta (orden de las fuentes, sin información, sin imágenes, falla de la consulta de imágenes).
- **Servicio**: firma inválida, evento ignorado, lote, duplicado, no texto, pregunta larga, sin información, 403 y 429, límite por persona (un solo aviso), cola con descarte, tope mensual, saludo una vez en 24 h, destino sin teléfono, partición, formato, imagen que falla, y que ningún texto por defecto contiene contacto.
- **Sin regresiones**: las pruebas existentes pasan y `POST /query` responde igual con `images: []`.

## 2. Recorrer el flujo completo en la laptop (sin Kapso)

Con la API local, el simulador de Kapso y el bot:

```bash
# Terminal 1: API con la credencial del bot y las citas encendidas
BOT_SERVICE_KEY=clave-local QUERY_CITED_SOURCES=on ADMIN_KEY=admin-local uvicorn mia.api.main:app --reload
# Terminal 2: Kapso falso, imprime lo que el bot envía
python whatsapp/scripts/kapso_falso.py --puerto 9000
# Terminal 3: el bot apuntando al Kapso falso
cd whatsapp && MIA_API_URL=http://localhost:8000 BOT_SERVICE_KEY=clave-local KAPSO_API_KEY=x \
  KAPSO_WEBHOOK_SECRET=secreto KAPSO_API_URL=http://localhost:9000 uvicorn mia_whatsapp.main:app --port 8100
```

1. En el panel (`web/admin`, con `ADMIN_KEY`): crear un artefacto con los dominios de prueba, registrar un bot con `kapso_number_id` `111` y ese artefacto, y asociar una imagen a un documento (historias 3 y 4).
2. Enviar avisos firmados: `python whatsapp/scripts/enviar_webhook.py --secreto secreto --numero 111 "¿Cuándo es la matrícula?"`. El Kapso falso debe imprimir el saludo, la respuesta con `Fuentes:` y la imagen con su pie de foto (historias 1 y 2).
3. Repetir con el mismo `--id` (duplicado: una sola respuesta); con `--tipo audio`; con una pregunta de más de 500 caracteres; con una pregunta sin respuesta en los documentos (historias 1 y 6).
4. Enviar 11 mensajes seguidos con la misma persona (`--persona p1`): el undécimo recibe un solo aviso y los siguientes, nada (historia 5). Arrancar el bot con `BOT_MAX_CONCURRENT_QUERIES=1 BOT_QUEUE_SIZE=2` y lanzar una ráfaga: se descarta lo que excede la cola.
5. Reiniciar la API con `BOT_MONTHLY_MESSAGE_CAP=6` y enviar mensajes: al llegar a 6 el bot no envía nada más; el panel muestra el tope alcanzado y el consumo sobrevive a reiniciar el bot (historia 5).
6. **Cambio en caliente** (SC-006): sin reiniciar nada, cambiar desde el panel el artefacto asignado o los dominios del artefacto, y repetir una pregunta que solo está en el dominio nuevo: antes "sin información", después la respuesta. Desactivar el bot o el artefacto: el bot responde "no disponible" y otro artefacto sigue funcionando (historias 4 y 8).
7. Enviar un aviso con firma incorrecta (`--secreto equivocado`): 401 y nada procesado. Enviar un aviso de un `--numero` sin bot: se ignora y queda en el registro.

## 3. Medir (con la API local o la de producción en solo lectura de datos)

| Criterio | Cómo se mide |
|---|---|
| SC-001, tiempo hasta la respuesta | Las líneas del registro del bot traen `ms` por mensaje; con las preguntas de la batería del MVP (`scripts/pruebas_mvp.py`) y el Kapso falso, mediana bajo 5 s y p95 bajo 10 s. |
| SC-002, confirmación | El simulador mide el tiempo hasta el 200 con una consulta lenta (API con latencia simulada): siempre bajo 10 s, en la práctica milisegundos. |
| SC-003, imagen | Asociar `horario_matricula.png` y preguntar de cinco formas distintas: 5 de 5 con texto e imagen. |
| SC-004, sin información | Los casos "sin información" de la batería del MVP y de `scripts/datos/casos_busqueda.json` no reciben imagen, contacto ni respuesta inventada. |
| SC-009, costo por pregunta | El módulo **Uso** del panel, filtrado por el artefacto del bot: costo medio por consulta bajo 0,001 USD (línea base 0,0004). |
| SC-010, teléfonos | Buscar en la base (`queries`) y en los registros de la API y del bot cualquier teléfono de prueba usado: 0 coincidencias. |
| SC-011, regresión | `python scripts/pruebas_mvp.py` da 19 de 19 y las pruebas existentes pasan. |

## 4. El sandbox de Kapso (la prueba real de esta entrega, historia 7)

Es el único entorno real de esta entrega ([contracts/servicio-whatsapp.md](contracts/servicio-whatsapp.md), research R17). Solo le puede escribir tu teléfono, registrado como de prueba.

1. **Cuenta y sandbox** (sin costo ni Meta): en Kapso, *WhatsApp > Sandbox > Add Test Number* con tu teléfono; recibes un código de 6 caracteres (sensible a mayúsculas, vence a los 15 minutos) y el número del sandbox; lo envías desde tu teléfono con *Open WhatsApp* ([guía](https://docs.kapso.ai/docs/how-to/whatsapp/use-sandbox-for-testing.md)).
2. **Clave de la API de Kapso** (`X-API-Key`): del panel de Kapso; solo como variable `KAPSO_API_KEY` del servicio, nunca en el repositorio ni en el chat.
3. **Publicar el servicio** (paso 6) o abrir un túnel hacia el servicio local, para que Kapso pueda llamar al webhook.
4. **Webhook**: en la configuración *Sandbox WhatsApp* > *Manage Webhooks*, agregar la dirección `https://<dominio de mia-whatsapp>/webhooks/kapso` con el evento de mensaje recibido. Si el formulario no pide el secreto de firma, crear el webhook con la llamada de la API del paso 5 del despliegue (el secreto lo eliges tú y es el mismo `KAPSO_WEBHOOK_SECRET` del servicio).
5. **Descubrir el `phone_number_id` del sandbox**: la documentación no dice dónde está. Enviar un primer mensaje desde el teléfono: el servicio lo ignora (aún no hay bot) y deja en su registro `bot_desconocido` con el `number_id`. Copiarlo.
6. **Registrar el bot** en el panel con ese `number_id` y el artefacto de pruebas, y repetir los pasos 2 a 6 de la sección 2 con mensajes reales desde el teléfono.
7. **Comprobar las imágenes primero**: asociar una imagen a un documento y preguntar por él. Si el sandbox la rechaza (solo documenta texto e interactivos), el texto llega igual y el fallo queda en el registro: las imágenes se verifican con el Kapso falso hasta tener un número de producción (research R17). Anotar el resultado en research R9 y R17.
8. Anotar también lo que la documentación no cubría: la forma de la respuesta de Kapso a un envío, cuántos teléfonos admite el sandbox, cuánto dura la sesión y el aspecto del formato en el teléfono.

## 5. Pasar a producción (no se hace en esta entrega)

El camino está documentado en la sección 11 de [Definicion_Requerimientos_Bot_WhatsApp.md](../../docs/Definicion_Requerimientos_Bot_WhatsApp.md): cuenta de Meta, número, plan y cuota, webhook por número, revisión de dominios e imágenes públicas y qué ajustar. Nada de eso se implementa ni se valida aquí.

## 6. Desplegar para el sandbox (lo hace el usuario, en este orden)

1. Merge de `dev` a `main` y `git push origin main`.
2. Variables de la API en Railway (servicio `MIA`): `BOT_SERVICE_KEY` (un valor aleatorio largo), `BOT_MONTHLY_MESSAGE_CAP=1800`, `MAX_IMAGE_MB=2` y `QUERY_CITED_SOURCES=on` (con las otras cuatro del cierre de V3, [Definicion_Requerimientos_V3.md](../../docs/Definicion_Requerimientos_V3.md) sección 2.10). Agregarlas juntas y sin desplegar hasta el paso 3 (OPERACION.md, "Desplegar cambios").
3. `python scripts/servicios.py encender MIA`: la API migra la base a la `0007` al arrancar. Comprobar en los registros que aplicó `0006` y `0007`.
4. Crear en la interfaz de Railway el servicio `mia-whatsapp`: *Source > Root Directory* `whatsapp`, sin ruta en *Config-as-code* ni en *Dockerfile Path*; variables de [servicio-whatsapp.md](contracts/servicio-whatsapp.md) (la misma `BOT_SERVICE_KEY` de la API); generar el dominio. Luego `python scripts/servicios.py encender mia-whatsapp`.
5. Webhook en Kapso (sección 4, pasos 4 y 5). Para un número que no sea el del sandbox, el webhook se crea por número con `POST https://api.kapso.ai/platform/v1/whatsapp/phone_numbers/{phone_number_id}/webhooks`, el encabezado `X-API-Key` y el cuerpo `url`, `events` = `["whatsapp.message.received"]` y `secret_key`.
6. En el panel: crear un artefacto de pruebas (modo literal, tope diario bajo, dominios de prueba o públicos), registrar el bot con el `number_id` del sandbox y asociar imágenes a documentos de prueba.
7. Probar con un mensaje real desde el teléfono de prueba y revisar el consumo en el módulo Bots.

**Volver atrás**: desactivar el bot en el panel (o apagar `mia-whatsapp` con `python scripts/servicios.py apagar mia-whatsapp`) basta para dejar de responder, sin tocar la API. Para quitar también las imágenes y los bots de la base: `alembic downgrade 0005` **antes** de desplegar una versión anterior de la API (OPERACION.md, "Desplegar cambios"); se pierden los bots y las imágenes.
