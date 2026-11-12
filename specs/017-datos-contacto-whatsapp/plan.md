# Implementation Plan: Datos de contacto de quienes escriben al bot de WhatsApp

**Branch**: `dev` (feature `017-datos-contacto-whatsapp`, sin rama propia) | **Date**: 2026-11-12 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/017-datos-contacto-whatsapp/spec.md`

## Summary

El bot de WhatsApp guarda un **contacto por teléfono y por bot** en una tabla nueva y dedicada (`whatsapp_contacts`, migración `0012`) y, tras responder la primera pregunta de una persona nueva, le envía **en un mensaje aparte** la invitación a dejar nombre y correo (opcional, con aviso de qué se guarda). Las reglas de texto que reconocen correo, nombre, negativa, borrado y la máquina de estados de la conversación viven en el servicio `mia-whatsapp` (como la aclaración de la feature 013: solo reglas, sin modelo); la API solo almacena y valida, a través de rutas nuevas protegidas con la credencial de servicio del bot. El teléfono llega a la API únicamente en esas rutas (nunca en `/bot/query`, ni en Uso, ni en los registros). Un módulo nuevo del panel, solo para alcance global, lista, filtra, descarga en CSV y borra los contactos, con auditoría sin datos personales. Todo queda tras un ajuste del servicio (`BOT_CONTACT`, apagado por defecto) y una falla de la base nunca impide responder una pregunta.

Decisiones principales (detalle y alternativas en [research.md](research.md)):

- **Un viaje de ida y vuelta menos por mensaje**: el teléfono viaja en la misma llamada `POST /bot/messages` que ya cuenta el mensaje; la API devuelve el estado del contacto (R1).
- **La invitación se "reclama" de forma atómica** en la API antes de enviarla, así dos mensajes simultáneos o un reintento no producen dos invitaciones, y si el envío falla se revierte (R3).
- **Reglas conservadoras para el nombre** (con correo, con frase de presentación o de 2 a 4 palabras con mayúscula inicial), porque un falso positivo guarda una pregunta como si fuera un nombre; la confirmación del bot es la red de seguridad (R4).
- **El mensaje que responde la invitación nunca llega a la consulta ni al modelo**: lo consume el flujo de contacto (R5).
- **CSV en el servidor**, con el mismo patrón y la misma neutralización de fórmulas que ya tiene el registro de consultas (R7).

## Technical Context

**Language/Version**: Python 3.12+ (API `mia` y servicio `mia_whatsapp`), TypeScript con React 19 (panel `web/admin/`)

**Primary Dependencies**: FastAPI, SQLAlchemy y Alembic (API); FastAPI y `httpx` (servicio, que no importa `mia`); Mantine, TanStack Query y Vite (panel). Ninguna dependencia nueva.

**Storage**: tabla nueva `whatsapp_contacts` en la base SQL (SQLite en desarrollo, Postgres en producción), migración aditiva `0012`. Qdrant no interviene.

**Testing**: `pytest` en la raíz (API, incluido el recorrido de punta a punta en un solo proceso) y en `whatsapp/tests/` (servicio, con `httpx.MockTransport`); Vitest en `web/admin/`.

**Target Platform**: Railway (API y servicio `mia-whatsapp`), Neon (Postgres), sitio estático del panel.

**Project Type**: web-service (API) + servicio de webhooks + panel web. Sin proyectos nuevos.

**Performance Goals**: la respuesta a la primera pregunta no se retrasa por la invitación (se envía después); el contacto no agrega llamadas HTTP por mensaje (R1); el estado se guarda en menos de 2 segundos (SC-003).

**Constraints**: la cuota gratuita de Kapso (2.000 mensajes al mes entre recibidos y enviados; tope 1.800): la invitación cuesta 1 mensaje enviado por persona nueva y la confirmación 1 enviado más 1 recibido; el teléfono, el nombre y el correo no aparecen en Uso, en los registros ni en errores; sin vencimiento automático.

**Scale/Scope**: cientos o pocos miles de contactos (el tope mensual de mensajes lo acota); un módulo de panel, una ruta de servicio nueva (`PUT /bot/contacts`) y una ampliada (`POST /bot/messages`), tres rutas de administración, una tabla, una migración.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Evaluación |
|---|---|
| I. Almacenamiento y consulta desacoplados | **Cumple.** El servicio no accede a la base: guarda y lee contactos por la API con la credencial de servicio, igual que el resto del bot. Ningún artefacto nuevo duplica infraestructura. |
| II. Pipeline modular | **No aplica.** No toca loaders, embeddings, LLM ni almacén vectorial. |
| III. Independencia del proveedor de LLM | **Cumple.** El reconocimiento es por reglas de texto, sin llamar a ningún modelo; además los mensajes de contacto no llegan al modelo (R5). |
| IV. Extensibilidad de dominios | **No aplica.** Ningún dominio cambia; la migración es solo aditiva. |
| V. Trazabilidad de respuestas | **No aplica.** Las respuestas RAG no cambian (SC-007). |
| Datos sensibles de personas | **Cumple con una excepción declarada.** Los contactos no son un dominio de conocimiento ni se exponen a la consulta: solo la credencial de servicio y las cuentas de alcance global los leen. Se revierte de forma deliberada FR-027 y SC-010 de la feature 011 (no guardar el teléfono), acotada a la tabla nueva y documentada (FR-029). |
| Estilo (sin guion largo, español) | **Cumple**: aplica a todos los artefactos y al código. |

Sin violaciones: no hace falta la tabla de complejidad. **Re-evaluación tras el diseño (Phase 1): sin cambios**; las rutas de servicio y de administración quedan separadas, y el módulo del panel no puede leer contactos con permisos de programa.

## Project Structure

### Documentation (this feature)

```text
specs/017-datos-contacto-whatsapp/
├── plan.md                         # Este archivo
├── research.md                     # Decisiones R1 a R13 con alternativas
├── data-model.md                   # Tabla whatsapp_contacts y estados
├── quickstart.md                   # Validación de punta a punta
├── contracts/
│   ├── bot-contactos-api.md        # Rutas del servicio: /bot/messages ampliada y /bot/contacts
│   ├── contactos-admin-api.md      # Rutas del panel: /contacts (lista, CSV, borrado)
│   └── servicio-contactos.md       # Flujo, reglas de texto, textos y variables del servicio
├── checklists/requirements.md
└── tasks.md                        # Tareas de implementación (42)
```

### Source Code (repository root)

```text
src/mia/
├── contacts/                       # NUEVO: lógica de contactos, sin HTTP
│   ├── __init__.py
│   ├── store.py                    # obtener o crear, reclamar invitación, aplicar evento, borrar, consultar con filtros
│   ├── phone.py                    # normalización del teléfono (sin enmascarado: el teléfono nunca va a la auditoría)
│   └── csv_export.py               # CSV con BOM y neutralización de fórmulas (reutiliza el guardia de usage/log.py)
├── api/routes/
│   ├── bot_service.py              # AMPLÍA POST /bot/messages (phone opcional, contact en la respuesta); NUEVO PUT /bot/contacts
│   ├── contacts.py                 # NUEVO: GET /contacts (JSON y CSV), DELETE /contacts/{id}, DELETE /contacts (por filtro con conteo)
│   └── main.py (api/main.py)       # registra el router nuevo
└── storage/
    ├── models.py                   # AGREGA WhatsAppContact
    └── migrations/versions/0012_contactos_de_whatsapp.py

whatsapp/src/mia_whatsapp/
├── contacts.py                     # NUEVO: reglas de texto (correo, nombre, negativa, borrado, reapertura, "para qué") y armado de textos
├── api_client.py                   # AMPLÍA count_messages (phone, contact) y NUEVO put_contact / claim_invite
├── webhook.py                      # AMPLÍA IncomingMessage con `phone` (solo teléfono real, nunca el identificador de usuario)
├── flow.py                         # AMPLÍA _process: respuesta a la invitación, borrado, invitación tras la primera respuesta
├── config.py                       # BOT_CONTACT y textos BOT_TEXT_CONTACT_*
├── logs.py                         # campo `contacto` (solo el nombre del evento, sin datos)
└── state.py                        # sin cambios (la clave con hash y los límites siguen igual)

web/admin/src/
├── api/contacts.ts                 # NUEVO: lista, descarga, borrado
├── api/types.ts                    # AGREGA tipos de contacto
├── auth/capabilities.ts            # AGREGA canManageContacts (alcance global)
└── modules/
    ├── index.tsx                   # AGREGA la entrada "Contactos de WhatsApp"
    └── contactos/                  # NUEVO: ContactosPage, filtros, tabla, diálogo de borrado, utilidades y pruebas

tests/unit/
├── test_contacts_store.py          # estados, reclamo atómico, unicidad, concurrencia
├── test_contacts_service_api.py    # /bot/messages ampliada y /bot/contacts, credencial, validación
├── test_contacts_admin_api.py      # lista, filtros, CSV, borrado, permisos, auditoría sin datos
├── test_contacts_privacidad.py     # ni Uso, ni registros, ni errores traen teléfono, nombre o correo
├── test_migrations.py              # AMPLÍA: 0012 sube y baja
└── test_bot_end_to_end.py          # AMPLÍA: recorrido completo con la función encendida y apagada

whatsapp/tests/
├── test_contacts_rules.py          # casos de texto (correo, nombre, negativa, borrado, preguntas que no son datos)
└── test_flow_contacts.py           # orden de pasos, invitación aparte, cuota, fallas, apagado

docs/                               # ARQUITECTURA, OPERACION, Definicion_Requerimientos_Bot_WhatsApp, specs/011 (nota de la excepción)
```

**Structure Decision**: se mantiene la estructura existente: la lógica de datos va en un paquete `mia.contacts` sin HTTP (igual que `mia.bots` y `mia.chat`), las rutas en `api/routes/`, las reglas de conversación en el servicio (que no importa `mia` y habla con la API solo por HTTP) y el módulo del panel como una carpeta más en `web/admin/src/modules/`. No se agregan proyectos ni dependencias.

## Complexity Tracking

Sin violaciones de la constitución que justificar.
