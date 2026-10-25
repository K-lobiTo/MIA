# Data Model: Bot de WhatsApp con Kapso

Tres tablas nuevas en SQL (dos migraciones aditivas), un campo nuevo en la respuesta de la consulta y el estado transitorio del servicio del bot, que vive en memoria. No cambia ninguna tabla ni columna existente.

## Bot (tabla `bots`, migración `0006`)

Un canal de WhatsApp registrado: el número de Kapso al que responde y el artefacto con el que consulta.

| Campo | Tipo | Notas |
|---|---|---|
| `id` | texto (UUID) | clave primaria |
| `name` | texto | único; lo escribe quien administra (por ejemplo `Atracción de estudiantes`) |
| `kapso_number_id` | texto | único; el `phone_number_id` de Kapso del número (lo trae cada aviso); no es el teléfono de nadie |
| `artifact_id` | texto, nulo, clave foránea a `artifacts.id` | el artefacto asignado. La API siempre pide uno al registrar y al cambiar; es nulo solo si el artefacto desaparece (hoy no hay ruta que borre artefactos), y un bot sin artefacto responde "no disponible" |
| `active` | booleano | por defecto verdadero |
| `created_at` | fecha y hora | UTC sin zona |
| `updated_at` | fecha y hora | UTC sin zona, se actualiza al editar |

**Restricciones**: `name` único y `kapso_number_id` único. No hay borrado: se desactiva (BOT-5).

**Qué ve el bot hoy** no se guarda: se calcula en cada consulta con `configured_domain_ids(session, artifact)`, así un cambio de los accesos del artefacto o del artefacto asignado rige desde la consulta siguiente (BOT-3, BOT-4, SC-006).

**Estados de disponibilidad** (los calcula la API, ver [contracts/bot-servicio-api.md](contracts/bot-servicio-api.md)): `ok` (bot activo con artefacto activo y bajo el tope mensual), `disabled` (bot desactivado, sin artefacto o con el artefacto desactivado), `cap_reached` (tope mensual alcanzado) y `unknown_bot` (ningún bot tiene ese número).

## Consumo mensual (tabla `bot_message_counts`, migración `0006`)

Cuántos mensajes de WhatsApp usó un bot en un mes: los recibidos y los enviados.

| Campo | Tipo | Notas |
|---|---|---|
| `bot_id` | texto, clave foránea a `bots.id` | parte de la clave primaria |
| `month` | texto `AAAA-MM` | parte de la clave primaria; el mes calendario en la zona de `CAP_TIMEZONE` |
| `received` | entero | mensajes recibidos (por defecto 0) |
| `sent` | entero | mensajes enviados, contando cada texto y cada imagen (por defecto 0) |
| `updated_at` | fecha y hora | UTC sin zona |

**Reglas**: una fila por bot y mes; se crea al primer mensaje del mes (el contador de un mes nuevo nace en cero, sin tarea de reinicio). El consumo del mes es `received + sent`. Se actualiza con un incremento atómico en SQL (`received = received + n`); si no hay fila se inserta y, si otro proceso la insertó a la vez, se repite el incremento. Se conservan los meses anteriores (historial).

**Tope**: `BOT_MONTHLY_MESSAGE_CAP` de la API (1.800 por defecto), igual para todos los bots. Alcanzado cuando `received + sent >= tope` después de contar el mensaje que llega.

## Imagen de documento (tabla `document_images`, migración `0007`)

Una imagen PNG o JPG asociada a un documento. Un documento tiene varias, en un orden.

| Campo | Tipo | Notas |
|---|---|---|
| `id` | texto (UUID) | clave primaria, la que usa el panel |
| `document_id` | texto, clave foránea a `documents.id` | indexado junto con `position` |
| `public_id` | texto | único; `secrets.token_urlsafe(24)`; es lo que va en el enlace público y **cambia al reemplazar la imagen** |
| `content_type` | texto | `image/png` o `image/jpeg` |
| `content` | binario (`LargeBinary`) | la imagen; columna `deferred`: no se lee al listar |
| `size_bytes` | entero | para validar y mostrar sin leer el binario |
| `caption` | texto | descripción opcional (pie de foto), hasta 1.000 caracteres; por defecto vacío |
| `position` | entero | orden dentro del documento, desde 0 sin huecos |
| `created_by` | texto | correo de quien la subió, o `automatizacion` |
| `created_at` | fecha y hora | UTC sin zona |
| `updated_at` | fecha y hora | UTC sin zona, se actualiza al reemplazar o describir |

**Validación** (la API, ver [contracts/imagenes-api.md](contracts/imagenes-api.md)): por el contenido, no por el nombre. PNG: firma `89 50 4E 47 0D 0A 1A 0A` y termina con el trozo `IEND`. JPEG: empieza con `FF D8 FF` y termina con `FF D9`. Tamaño máximo `MAX_IMAGE_MB` (2 por defecto). Descripción de hasta 1.000 caracteres.

**Ciclo de vida**: se agrega (queda al final del orden), se describe, se reordena (la lista completa en una sola operación), se reemplaza (mismo registro, contenido y `public_id` nuevos: el enlace anterior deja de servir) y se quita (borrado físico; su enlace responde 404). Quitar una imagen compacta las posiciones. Un documento nuevo (otra versión del mismo archivo) es otro documento y no hereda las imágenes (limitación conocida de la spec).

**Si algún día se agrega una ruta que borre documentos**, debe borrar antes sus imágenes: la clave foránea no tiene borrado en cascada (como las demás tablas).

## Respuesta de la consulta (campo nuevo `images`)

`QueryResponse` gana `images: list[Image]`, por defecto lista vacía:

| Campo de `Image` | Notas |
|---|---|
| `url` | ruta relativa `/media/{public_id}`; quien la use la completa con la dirección pública de la API |
| `caption` | la descripción de la imagen, o vacío |
| `document` | el nombre del archivo del documento al que pertenece |

Orden: el de las fuentes de la respuesta (cada documento una vez, en su primera aparición) y, dentro de un documento, el de `position`. Vacía si la respuesta es "sin información", si ningún documento citado tiene imágenes o si la consulta de imágenes falla. Los clientes que no la conocen la ignoran: los demás artefactos no cambian.

## Estado del servicio del bot (solo memoria, no se persiste)

Todo vive en el proceso del bot, con vigencia y tamaño acotado (research R8). Se pierde al reiniciar y se acepta para el prototipo.

| Estado | Contenido | Vigencia y tope |
|---|---|---|
| Mensajes vistos | `message.id` (y `X-Idempotency-Key`) con la hora de llegada | 24 h; hasta 50.000 entradas |
| Límite por persona | para cada clave de persona, las horas de los mensajes aceptados (última hora y último día) y si ya recibió el aviso de espera | ventanas de 1 h y 24 h; hasta 50.000 personas |
| Saludo | la hora del último saludo por clave de persona | 24 h |
| Consultas | semáforo de 5 y contador de espera con tope de 20 | por proceso |
| Envíos a Kapso | horas de los últimos envíos para no pasar de 100 por minuto | 1 min |

**Clave de persona**: SHA-256 de una sal aleatoria del proceso más el identificador disponible. El teléfono no se guarda ni se escribe en el registro.

## Relaciones

```
Unit 1--* Domain 1--* Document 1--* DocumentImage
Artifact 1--* Bot (un artefacto puede estar asignado a varios bots)
Bot 1--* BotMessageCount (una fila por mes)
Artifact 1--* QueryLog   (las consultas del bot se registran con el artefacto asignado)
```

## Migraciones

- **`0006_bots`** (`down_revision = "0005"`): crea `bots` y `bot_message_counts`. Sin semillas: el bot se registra desde el panel. `downgrade` borra las dos tablas.
- **`0007_imagenes_de_documentos`** (`down_revision = "0006"`): crea `document_images` con su índice. `downgrade` borra la tabla (las imágenes se pierden: exportarlas antes si se quieren conservar).
- Las dos son solo aditivas e idempotentes en la práctica (crean tablas nuevas). La API migra al arrancar: no desplegar una versión con menos migraciones que las de la base (OPERACION.md, "Desplegar cambios"); para volver atrás, `alembic downgrade 0005` antes.
