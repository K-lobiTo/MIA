# MIA: Definición de Requerimientos de la Versión 3

**Qué es este documento:** punto de partida de los requerimientos de la tercera versión de MIA. **Es un borrador abierto: de momento solo recoge un requerimiento, y su implementación se deja para después** (decisión del 2026-10-13). Parte del estado descrito en [Definicion_Requerimientos_V2.md](Definicion_Requerimientos_V2.md) y [ARQUITECTURA.md](ARQUITECTURA.md). Los otros candidatos para esta versión ya están listados en la sección 10 del documento de la versión 2 y se incorporarán aquí cuando se decida su alcance.

## 1. Alcance acordado hasta ahora

| Id | Tema | Estado |
|---|---|---|
| BUS-1 a BUS-4 | Responder consultas que no coinciden de forma directa con el texto de los documentos (sección 2) | Requerimiento definido, **implementación pendiente** |

## 2. Consultas no directas

### 2.1 Qué se quiere

Que la Consulta administrativa (y cualquier artefacto que use `POST /query`) responda bien preguntas formuladas con las palabras de una persona y no con las del documento, como lo hace una herramienta del tipo NotebookLM. Hoy una pregunta correcta puede terminar en "No encontré información suficiente" solo porque se parece poco al texto.

### 2.2 Casos que hoy fallan

| Caso | Pregunta que falla | Variante que sí responde | Qué pasa |
|---|---|---|---|
| Pregunta sobre una persona | "¿Quién es *nombre y apellidos*?" (observado el 2026-10-13 en modo con razonamiento) | Escribir solo "*nombre y apellidos*" | La respuesta "sin información" llegó en 0,1 s, o sea sin consultar al modelo: ningún fragmento superó el umbral de similitud. Con solo el nombre sí lo superó y el documento se encontró. |
| Siglas | "¿Qué líneas de trabajo final de graduación ofrece la maestría?" (prueba del 2026-10-06, ver [PRUEBAS_MVP.md](PRUEBAS_MVP.md)) | Preguntar con "TFG" | La forma desarrollada no alcanza el umbral contra un documento que usa la sigla. |

Los dos casos tienen la misma causa: el sistema descarta los fragmentos cuya similitud con la pregunta queda bajo `QUERY_SIMILARITY_THRESHOLD` y, si no queda ninguno, responde "sin información" sin llamar al modelo (`src/mia/api/routes/query.py`). Una pregunta completa ("¿Quién es X?") se parece menos a un fragmento que el nombre solo. Es un diagnóstico por lectura del código y de las pruebas anteriores: no se han medido los puntajes reales.

### 2.3 Requerimientos

| Id | Requerimiento |
|---|---|
| BUS-1 | Una pregunta sobre un nombre propio, una sigla o un término que aparece en los documentos debe encontrar esos documentos aunque la pregunta tenga palabras de más ("¿Quién es X?", "¿Qué es el TFG?", "háblame de X"). |
| BUS-2 | Una pregunta con la forma desarrollada de una sigla, o con la sigla cuando el documento usa la forma desarrollada, debe encontrar el mismo documento. |
| BUS-3 | Ningún cambio debe aumentar de forma notable las respuestas inventadas: cuando los documentos de verdad no tienen la información, la respuesta sigue siendo "sin información suficiente". |
| BUS-4 | Los topes de gasto (por artefacto y de toda la API) se siguen respetando, y el costo adicional por consulta, si lo hay, queda visible en el módulo Uso. |

### 2.4 Cómo funciona NotebookLM (referencia)

Google no publica el detalle. Por lo que se sabe y se deduce, la diferencia principal con MIA es que no hay una puerta de similitud antes del modelo: se le pasan los fragmentos más cercanos (o documentos enteros, gracias a un contexto muy largo) y es el modelo, que entiende el lenguaje, quien decide si hay respuesta. A eso suelen sumarse técnicas habituales como reformular la pregunta, combinar búsqueda por palabras exactas y por significado, y reordenar los resultados. No hay confirmación de cuáles usa NotebookLM.

### 2.5 Opciones de solución (sin decidir)

| Opción | Qué cambia | Costo y riesgo |
|---|---|---|
| A. Bajar el umbral de similitud | Variable de entorno en Railway, sin código. | Más fragmentos poco relacionados llegan al modelo y más consultas sin respuesta lo llaman (cuestan). Hay que recalibrar con las preguntas de prueba. |
| B. Segundo intento con la pregunta "limpia" | Si ningún fragmento pasa el umbral, repetir la búsqueda sin la envoltura de la pregunta ("¿Quién es X?" pasa a "X"). Por reglas, sin modelo. | Bajo costo y riesgo. Cubre nombres y "qué es X", no las siglas. |
| C. Umbral distinto por modo | Con razonamiento (que ya filtra con el modelo) aceptar un umbral más bajo y más fragmentos. | La consulta cuesta más cuando entra ruido. |
| D. Búsqueda híbrida (palabras exactas y significado) | Esquema de Qdrant con vectores dispersos y reindexación completa. | El cambio más grande. Es la solución de fondo para nombres propios y siglas. |

Recomendación provisional: empezar por B, medir con un registro del mejor puntaje de las consultas que terminan en "sin información", y con esos datos decidir si hacen falta A o C. D se reserva para cuando haya más preguntas de este tipo. Una forma de acercarse al comportamiento de NotebookLM (pasar siempre los fragmentos más cercanos y dejar que el modelo decida) es la opción C llevada al extremo; su costo depende de cuánto gasto extra por consulta sin respuesta se acepte.

### 2.6 Decisiones pendientes

1. **Cuánto gasto extra por consulta sin respuesta se acepta.** Decide entre bajar el umbral (A, C) y reformular sin modelo (B).
2. **Si se permite consultar a Qdrant de producción para medir los puntajes.** La medición solo imprimiría puntajes, nunca el texto de los fragmentos, porque contienen datos personales.
3. **Cuántos casos de prueba hacen falta** (nombres, siglas, preguntas indirectas) para calibrar y para comprobar BUS-3. Se propone reutilizar los 15 de [PRUEBAS_MVP.md](PRUEBAS_MVP.md) y sumar los dos casos de la sección 2.2.

### 2.7 Criterios de aceptación (borrador)

- Los dos casos de la sección 2.2 responden con la pregunta completa igual que con la variante corta.
- Los 15 casos de [PRUEBAS_MVP.md](PRUEBAS_MVP.md) siguen respondiendo bien.
- Una pregunta sobre un tema que no está en ningún documento sigue respondiendo "sin información suficiente".
- El costo medio por consulta de los modos literal y con razonamiento, medido en el módulo Uso, no sube más de lo que se decida en la decisión pendiente 1.
