# Contrato: la memoria del artefacto en la API de administración, `/config` y el panel

Cambios de las rutas de artefactos del panel y de `GET /config`. Datos en [data-model.md](../data-model.md); decisiones en [research.md](../research.md) R5 y R7.

## Artefactos (`POST /artifacts`, `PATCH /artifacts/{id}`, `GET /artifacts`)

- `ArtifactCreate` y `ArtifactUpdate` aceptan `context_turns`: entero de **0 a 10** (`Field(ge=0, le=10)`); fuera de rango o no numérico responde **422** con el mensaje de validación y no cambia nada. En la creación vale 0 si no se envía.
- `ArtifactOut` devuelve `context_turns` (siempre presente; 0 en los artefactos existentes).
- Mismo alcance que el resto de los parámetros del artefacto (`artifact_in_scope`): una persona de alcance de programa lo edita en los artefactos de su programa; fuera de su alcance responde 404 como hoy.
- Rige desde la consulta siguiente (`run_query` lo lee en cada consulta), sin reiniciar nada.
- **Registro de administración**: un cambio de `context_turns` deja una línea `artifact.context_turns` en `mia.admin` con `actor`, `target` = id del artefacto y `detail` = `"<nombre>: <anterior> -> <nuevo>"`, además de la línea `artifact.update` de siempre.

## Configuración (`GET /config` con la clave de un artefacto)

`artifact` agrega `context_turns`:

```json
{ "artifact": { "name": "Consulta Computación", "active": true, "context_turns": 3 } }
```

Sin clave de artefacto la respuesta no cambia (no hay artefacto). Un cliente que no conozca el campo lo ignora.

## Panel (módulo Artefactos)

| Pieza | Detalle |
|---|---|
| Formulario (`ArtifactForm.tsx`) | Campo numérico **Memoria de conversación (vueltas)**, de 0 a 10, con el valor actual y este texto: "Cuántas preguntas y respuestas anteriores recuerda este artefacto en cada conversación. Con más memoria las preguntas de seguimiento ('¿y cuánto cuesta?') se entienden, pero cada consulta lleva más texto y cuesta más. 0 es el comportamiento de siempre." |
| Tarjeta (`ArtifactCard.tsx`) | Muestra "Memoria: N vueltas" (o "Sin memoria" con 0) junto a los topes y modos. |
| Validación | Entero de 0 a 10 antes de enviar; el servidor es quien hace cumplir el rango. |
