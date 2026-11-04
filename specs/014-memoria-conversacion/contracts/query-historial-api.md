# Contrato: `POST /query` con historial

Cambio de `POST /query` (la consulta de los artefactos con su clave). Detalle de los datos en [data-model.md](../data-model.md) y decisiones en [research.md](../research.md) R1 a R4.

## Pedido

```json
{
  "domains": ["..."],
  "question": "¿y cuánto cuesta?",
  "mode": "literal",
  "history": [
    { "question": "¿Cuándo empiezan las lecciones de la maestría en analítica?", "answer": "Inician el 5 de octubre de 2026.", "mode": "literal" }
  ]
}
```

`history` es **opcional** (por defecto vacío): un cliente que no lo envía, o que envía `[]`, funciona exactamente como antes. Cada vuelta es `{question, answer, mode?}` con `extra="forbid"`.

## Cuándo se usa

| Situación | Qué hace la API |
|---|---|
| `context_turns` del artefacto en **0** | Ignora el historial por completo: no cambia la búsqueda, ni lo que ve el modelo, ni el costo. |
| `context_turns` mayor que 0 | Lo valida, descarta las vueltas "sin información", recorta a las últimas `context_turns` vueltas y por tamaño según el modo (data-model), y lo usa. |
| Historial con un campo que no es de la vuelta (`role`, etc.) | **422** (`extra="forbid"`): no hay forma de enviar un mensaje de sistema. |
| Más de 50 vueltas, textos vacíos o más largos que el máximo de entrada, `mode` inválido | **422**. |
| Historial que, tras las exclusiones, queda vacío | Se responde como una consulta sin historial. |

## Qué cambia en la consulta

1. **Búsqueda.** Si hay historial vigente y la pregunta es un seguimiento (`is_followup`), `HISTORY_REFORMULATION` decide la pregunta de búsqueda (`rules`: las últimas dos preguntas anteriores más la actual; `model`: una llamada corta que la reescribe; `off`: ninguna) y con ella se calcula el embedding, la búsqueda híbrida, el reranker y la pregunta limpia. Una pregunta que se entiende sola no se reformula.
2. **Respuesta.** El modelo recibe la **pregunta original** y, antes del contexto, un bloque rotulado "Conversación anterior (solo para entender la pregunta; no es una fuente de datos)" con las vueltas vigentes; la instrucción de sistema del modo lleva el párrafo `HISTORY_INSTRUCTIONS` (el historial nunca es fuente: toda respuesta sale solo de los fragmentos). Las fuentes, las imágenes, el formato y el "sin información" son los de siempre.
3. **Registro de Uso.** `QueryLog.question` es la pregunta actual (la original). El historial no se registra. El costo incluye el texto adicional del historial (ya está en el costo real del modelo) y, con `HISTORY_REFORMULATION=model`, el costo de la reescritura.
4. **Topes.** El chequeo de topes (del día y del modo) es previo y es el mismo: un artefacto que alcanzó su tope se rechaza (429) aunque traiga historial.

## Lo que no cambia

- Respuesta (`QueryResponse`), rechazos y códigos (401, 403, 404, 429, 502).
- `POST /bot/query`: construye su pedido **sin historial**; el bot no cambia de comportamiento.
- `GET /domains`, `POST /query/{id}/feedback` y el resto de las rutas.
