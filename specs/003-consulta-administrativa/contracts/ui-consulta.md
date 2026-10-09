# Contrato: interfaz de la Consulta

Qué llamadas hace la Consulta, en qué momento, y qué muestra en cada estado. Todos los textos en
español y sin guion largo.

## Llamadas

| Momento | Llamada | Uso |
|---|---|---|
| Al abrir con clave, y al volver a la pestaña | `GET /config` con `X-Artifact-Key` | Nombre (encabezado y `<title>`), modos visibles y disponibles, topes |
| Al abrir con clave | `GET /domains` con `X-Artifact-Key` | Dominios permitidos, agrupados por `unit_name` |
| Al enviar | `POST /query` | Respuesta; tiempo de espera 200 s |
| Tras 403 o 429 de `/query` | Volver a pedir `GET /config` y `GET /domains` | FR-018 |
| Al calificar | `POST /query/{id}/feedback` | `{"rating": "util" \| "no_util", "comment": "..."}` |

Cualquier 401 borra la clave guardada y vuelve a la pantalla de clave con el aviso
"La clave guardada ya no es válida. Ingresa la vigente (te la da quien administra MIA)."

## Pantallas y estados

**Sin clave**: campo para la clave, botón "Entrar", explicación de dónde se obtiene. No muestra
dominios ni nombre de instancia (el `<title>` es "MIA: Consulta").

**Con clave**:

- Encabezado y `<title>`: `artifact.name` de `/config`.
- Panel de dominios (lateral en computadora, desplegable en celular): casillas por dominio, agrupadas
  por unidad si hay más de una; acciones "Todos" y "Ninguno". Sin dominios permitidos: "Esta Consulta
  todavía no tiene dominios para consultar."
- Selector de modo (solo si hay más de un modo visible): nombre y descripción de cada modo; un modo no
  disponible aparece deshabilitado con su `reason`.
- Área de conversación vacía: ejemplos de preguntas por modo (texto fijo, no enviado).
- Campo de pregunta: Enter envía, Mayúsculas+Enter agrega una línea; máximo 2000 caracteres.

**Envío bloqueado** (cualquiera de estas, con el motivo junto al botón):

| Condición | Mensaje |
|---|---|
| Ningún dominio seleccionado | "Elige al menos un dominio." |
| Consulta en curso | (botón deshabilitado, sin mensaje) |
| `caps.cap_reached` o `caps.global_cap_reached` | El `reason` del modo, que ya dice que se reinicia a la medianoche |
| Modo elegido no disponible y ningún otro disponible | El `reason` del modo |

**Esperando respuesta**: burbuja con "Buscando en N dominios..."; en modo con razonamiento además
"El modo con razonamiento puede tardar más de un minuto."

**Respuesta con información**: texto con formato (negritas y listas); debajo "Fuentes": documentos
únicos con su dominio, y un desplegable "Ver fragmentos (N)". Pie: "Literal · 3,2 s" o
"Con razonamiento · 41 s". Botones "Útil" y "No útil"; al elegir uno aparece un campo opcional de
comentario con "Enviar comentario". La calificación elegida queda marcada y se puede cambiar.

**Respuesta sin información** (`no_info: true`): estilo distinto (fondo neutro, ícono informativo),
sin fuentes; también se puede calificar.

**Error**:

| Estado HTTP | Mensaje | Acciones |
|---|---|---|
| sin conexión | "No se pudo conectar con MIA. Revisa tu conexión." | Reintentar |
| tiempo agotado (200 s) | "MIA tardó demasiado en responder." | Reintentar; en razonamiento, "Reintentar en modo literal" |
| 502 | "El modelo de lenguaje no está disponible en este momento." | Reintentar; en razonamiento, "Reintentar en modo literal" |
| 429 | El `detail` de la API (dice qué tope y cuándo se reinicia) | En razonamiento, "Reintentar en modo literal" si el literal está disponible |
| 403 desactivado | El `detail` de la API y "Comunícate con quien administra MIA." | Ninguna |
| 403 permisos | El `detail` de la API; los dominios se actualizan | Reintentar (con la selección actualizada) |
| 422 | "La pregunta no es válida (máximo 2000 caracteres)." | Ninguna; lo escrito se conserva |

Reintentar envía la misma pregunta como un intercambio nuevo; el fallido queda en la conversación.

## Diseño

- Modo claro y oscuro con variables de color en `:root` y `@media (prefers-color-scheme: dark)`.
- Utilizable desde 360 px de ancho sin desplazamiento horizontal.
- Respuestas y fragmentos siempre como texto (React escapa); nunca HTML del modelo.
