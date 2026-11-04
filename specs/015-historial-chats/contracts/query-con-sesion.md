# Contrato: `POST /query` con sesión, `/config` y `artifacts.require_login`

Cambios de `POST /query`, de `GET /config` y de las rutas de artefactos. Datos en [data-model.md](../data-model.md); decisiones en [research.md](../research.md) R5, R6 y R7. **Sin sesión nada de esto cambia el comportamiento de hoy.**

## `POST /query`

Se agregan, ambos opcionales:

- Encabezado `X-Session-Token`: la sesión de un usuario (se suma a `X-Artifact-Key`, que sigue siendo obligatoria y la que autoriza: permisos, modos, dominios y topes son los del artefacto).
- Cuerpo `conversation_id`: la conversación a continuar. Sin él, y con sesión, se crea una nueva con esta pregunta.

| Situación | Qué hace |
|---|---|
| Sin `X-Session-Token`, artefacto sin `require_login` | Exactamente como hoy (la 014 incluida: usa el `history` del cliente si el artefacto tiene memoria). Respuesta `QueryResponse` sin campos nuevos; **no se guarda nada**. |
| Sin `X-Session-Token`, artefacto con `require_login` | **401** `{ "detail": "Este artefacto exige iniciar sesión...", "code": "login_required" }`. Se rechaza antes de buscar, sin costo; queda como rechazo en Uso (`outcome` `rejected_permission`). Solo aplica a `POST /query`: `POST /bot/query` no lo comprueba, así que un artefacto asignado a un bot sigue respondiéndole. |
| Token presente pero inválido, vencido o de un usuario desactivado | **401** `session_invalid`, con o sin `require_login`. |
| Sesión válida y guardado activo | Antes de buscar: **404** si `conversation_id` no es del usuario; **409** `conversation_full` si ya tiene `CHAT_MAX_TURNS` vueltas; **409** `too_many_conversations` si es nueva y el usuario ya tiene `CHAT_MAX_CONVERSATIONS` (todos sin llamar al modelo). El `history` que traiga el cuerpo se **ignora**: el historial sale de las últimas vueltas guardadas, recortado por la memoria del artefacto de la 014 (`context_turns`; con 0 no hay historial). Responde con `QueryResponseChat`. |
| Sesión válida y `CHAT_RETENTION_DAYS=0` | Como sin sesión: no se guarda, no se crea conversación, se usa el `history` del cliente como en la 014; la respuesta no trae `conversation_id`. |

### Respuesta con sesión (`QueryResponseChat`)

El `QueryResponse` de siempre más:

```json
{ "conversation_id": "uuid", "saved": true }
```

`saved` es falso si guardar la vuelta falló: la respuesta se entrega igual, `conversation_id` es el de la conversación a la que habría ido (nulo si no llegó a crearse) y el servidor registra el fallo sin textos. Las consultas que fallan (errores, topes, permisos) no guardan nada. Las respuestas de "sin información" sí se guardan (`no_info` verdadero).

El registro de Uso no cambia: la pregunta actual de la consulta, sin historial ni respuestas ni enlace a la conversación.

## `GET /config`

Con la clave del artefacto, `artifact` agrega `require_login` y la respuesta agrega `chat`:

```json
{
  "artifact": { "name": "Consulta Computación", "active": true, "context_turns": 3, "require_login": false },
  "chat": { "enabled": true, "retention_days": 90 }
}
```

`chat.enabled` es falso cuando `CHAT_RETENTION_DAYS` es 0. Sin clave de artefacto la respuesta no cambia. Un cliente que no conozca los campos los ignora.

## Artefactos (`POST /artifacts`, `PATCH /artifacts/{id}`, `GET /artifacts`)

- `ArtifactCreate` y `ArtifactUpdate` aceptan `require_login` (booleano; por defecto falso). `ArtifactOut` lo devuelve siempre.
- Mismo alcance que el resto de los parámetros del artefacto; rige desde la consulta siguiente, sin reiniciar.
- Un cambio deja la línea `artifact.require_login` en `mia.admin` (`detail` = `"<nombre>: false -> true"`), además de `artifact.update`.

## Panel (módulo Artefactos)

| Pieza | Detalle |
|---|---|
| Formulario (`ArtifactForm.tsx`) | Interruptor **Exigir inicio de sesión para consultar**, con el texto: "Si está activo, este artefacto solo responde a personas con usuario. Desactivado, cualquiera con la clave puede consultar (sin guardar conversaciones)." |
| Tarjeta (`ArtifactCard.tsx`) | Muestra "Exige sesión" o "Sin sesión". |

## `POST /bot/query` y `POST /bot/messages`

Sin cambios. El bot no usa usuarios ni guarda conversaciones.
