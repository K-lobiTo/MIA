# Research: Consulta administrativa de MIA

Decisiones técnicas tomadas para el plan. Cada una con lo elegido, el porqué y lo que se descartó.

## 1. Instrucción al modelo por modo

**Decision**: la instrucción al modelo (el mensaje de sistema) pasa a ser un parámetro de
`LLMProvider.answer(question, context, instructions)`. `src/mia/rag/modes.py` define la instrucción
de cada modo junto con su proveedor y modelo: el literal usa `RAG_SYSTEM_PROMPT` sin cambios y el
razonamiento una instrucción nueva, `REASONING_SYSTEM_PROMPT`, en `src/mia/rag/llm.py`. Todos los
proveedores reciben la instrucción en lugar de importar la constante.

**Rationale**: es la forma menos invasiva de que cada modo tenga su instrucción sin crear proveedores
nuevos (Principio II: la interfaz sigue siendo una sola y cada proveedor es intercambiable). La
instrucción vive en el código, no en una variable de entorno, porque es parte del comportamiento
verificable del sistema (SC-002) y cambiarla debe pasar por pruebas.

**Alternatives considered**: un proveedor por modo (duplica clientes y caché); instrucción por
variable de entorno (fácil de romper sin pruebas y difícil de leer en Railway); construir la
instrucción en `query.py` y pasar el mensaje completo (mezcla la ruta HTTP con el formato del modelo).

## 2. Contenido de la instrucción con razonamiento

**Decision**: misma base que la literal (solo los fragmentos, nada de conocimiento externo, español,
Markdown simple, la marca `SIN_INFORMACION` cuando ningún fragmento trata el tema), más:

- Puede combinar, comparar, contar y calcular con datos de varios fragmentos.
- Toda respuesta con información tiene dos partes fijas, en este orden y con estos títulos en negrita
  (no encabezados `#`): **Lo que dicen los documentos** (cada dato usado, con el nombre del documento
  de donde sale) y **Cálculo o conclusión** (la operación con sus números, por ejemplo
  `4 + 4 + 4 = 12`, y el resultado, o lo que se deduce y por qué).
- Si falta un dato para el cálculo, lo dice en la segunda parte en lugar de suponerlo.

**Rationale**: implementa FR-011 y la aclaración de la sesión 2026-10-08. Títulos en negrita porque
el formateador de la Consulta ya soporta negritas y listas (sección 3.2, CON-4) y no hace falta
soportar encabezados; igual se tratan las líneas que empiezan con `#` como texto en negrita por si
el modelo no obedece.

**Alternatives considered**: dejar el formato libre (no verificable en pruebas); pedir JSON con las
dos partes (más frágil con modelos de razonamiento y obliga a otro contrato de respuesta).

## 3. Cantidad de fragmentos por modo

**Decision**: `QUERY_SEARCH_LIMIT` (8) sigue siendo el del modo literal y se agrega
`QUERY_SEARCH_LIMIT_RAZONAMIENTO` (16). `ModeConfig` incluye `search_limit`; `query.py` lo usa en
lugar de `settings.query_search_limit`. Los vecinos (`QUERY_CONTEXT_NEIGHBORS`) y los documentos
completos cortos (`QUERY_FULL_DOCUMENT_MAX_CHUNKS`) se aplican igual en ambos modos.

**Rationale**: FR-012 pide 16 por defecto y ajuste por configuración. Con 16 resultados, vecinos y
documentos completos, el contexto queda en el orden de 20 000 a 40 000 tokens, dentro de lo que
aceptan los modelos configurados, y el costo estimado (unos 0.02 a 0.05 USD por consulta con
GLM 5.3) está cubierto por los topes. `OPENROUTER_MAX_TOKENS` (8000) limita la salida, razonamiento
incluido, y ya se probó con esfuerzo medio.

**Alternatives considered**: un multiplicador sobre el límite literal (menos claro de configurar);
más vecinos en vez de más resultados (no trae datos de más documentos, que es el objetivo).

## 4. Respuesta "sin información" en el contrato

**Decision**: `POST /query` agrega el campo `no_info: bool` a la respuesta. La Consulta lo usa para
distinguir esa respuesta (CON-6) en lugar de comparar el texto.

**Rationale**: el cliente actual compara el comienzo del texto, lo que se rompe si cambia la frase.
El dato ya existe en la API (`outcome = "no_info"`); exponerlo es un cambio compatible.

**Alternatives considered**: seguir comparando el texto (frágil); devolver `outcome` completo (expone
valores internos que la Consulta no necesita).

## 5. Largo máximo de la pregunta

**Decision**: `QueryRequest.question` con `max_length=2000` (422 si se supera). La Consulta limita el
campo a 2000 caracteres y muestra el contador cerca del límite.

**Rationale**: caso borde del spec ("pregunta demasiado larga"). Sin límite, una pregunta enorme
encarece la consulta y la embebe completa. 2000 caracteres cubren cualquier pregunta administrativa
real.

**Alternatives considered**: sin límite (riesgo de costo y abuso); 500 (corta preguntas con contexto).

## 6. Stack de la Consulta

**Decision**: el mismo del panel: React 19, TypeScript 5, Vite 6 y TanStack Query 5, en
`web/consulta/`, sin router (una sola pantalla). Pruebas con Vitest para las funciones puras.

**Rationale**: sección 7 del documento de requerimientos; un solo stack de frontend en el proyecto.
TanStack Query resuelve la carga y el refresco de `/config` y `/domains` (FR-018) sin código propio.

**Alternatives considered**: mantener el cliente sin framework de `web/` (la aclaración del
2026-10-08 decidió un cliente nuevo; con estados como topes, modos, reintentos y calificación, el
código sin framework crece mal).

## 7. Cliente de la API compartido entre panel y Consulta

**Decision**: no se crea un paquete compartido todavía. La Consulta tiene su propio
`src/api/client.ts`, con el mismo patrón que el del panel (base `VITE_API_URL` o `/api`, `ApiError`
con `status` y `detail`, clave en `localStorage` con `try/catch`), pero con `X-Artifact-Key` y un
tiempo de espera de 200 s.

**Rationale**: comparten unas 40 líneas, con encabezado, manejo de clave y tiempo de espera
distintos. Un paquete compartido (workspaces de npm o alias de Vite) agrega configuración de
compilación y publicación en dos sitios estáticos por poco código. Se mantiene la decisión 11 de
specs/002; se revisa si aparece un tercer artefacto.

**Alternatives considered**: carpeta `web/shared/` importada con alias (acopla las dos compilaciones
y los `tsconfig`); workspaces de npm (más infraestructura que código compartido).

## 8. Formato seguro de las respuestas

**Decision**: un formateador propio, función pura que convierte el texto en una lista de bloques
(párrafo, lista con viñetas, lista numerada) con segmentos en negrita, y un componente React que los
dibuja. Nunca se usa `dangerouslySetInnerHTML`: React escapa el texto (FR-021).

**Rationale**: es el mismo subconjunto que ya resuelve `web/src/format.ts` (negritas y listas), ahora
sin generar HTML. Una biblioteca de Markdown completa es más de lo que se necesita y abre la puerta a
HTML embebido.

**Alternatives considered**: `react-markdown` (dependencia más pesada, hay que desactivar HTML);
reutilizar `format.ts` con `innerHTML` (depende de escapar bien a mano).

## 9. Tiempo de espera y una consulta a la vez

**Decision**: `fetch` con `AbortController` a 200 s para `/query`; 30 s para el resto. Mientras una
consulta está en curso, el envío se deshabilita (FR-019). En desarrollo el proxy de Vite usa 200 s,
como el panel.

**Rationale**: sección 5 del documento de requerimientos y caso borde del spec. Con Railway la API no
se duerme, pero el razonamiento puede tardar decenas de segundos.

## 10. Disponibilidad de modos y envío

**Decision**: una función pura `resolveAvailability(config)` decide, a partir de `GET /config` con la
clave: qué modos mostrar (los permitidos), cuáles deshabilitar y con qué motivo, si el envío está
bloqueado (tope total o de toda la API) y el modo efectivo cuando el guardado ya no está disponible.
Ante un 403 o 429 de `/query`, la Consulta invalida `config` y `domains` para refrescarlos (FR-018).

**Rationale**: concentra en una función probable con Vitest las reglas de CON-2 y CON-3 y los casos
borde del modo guardado, sin depender de la red.

## 11. Publicación de las dos instancias

**Decision**: dos servicios de Railway dentro del proyecto de la API, ambos desde este repositorio con
`Root Directory` `web/consulta`, el mismo `Dockerfile` (compila con Vite y sirve `dist` con `serve`) y la
misma `VITE_API_URL` apuntando a la API. Nombres sugeridos: `mia-computacion` y `mia-administracion`.
Sus direcciones (`*.up.railway.app`) se agregan a `CORS_ORIGINS`. Se documenta en `docs/OPERACION.md`;
crear los servicios lo hace quien administra MIA. El panel de administración no se publica: se corre en
la computadora de quien lo usa.

**Rationale**: la sección 7 pide una compilación publicada dos veces con direcciones separadas, para
que cada instancia tenga su propio almacenamiento (FR-023). Como no hay configuración por instancia en
la compilación (FR-003), las dos compilaciones son idénticas. Se eligió Railway (cambio del
2026-10-08, antes se había pensado en Render Static Sites) porque permite apagar un sitio de forma
remota con *Remove* y volver a encenderlo con *Redeploy* (compartir el enlace solo cuando se necesita)
sin dejar de gastar mientras está apagado. Un `Dockerfile` en `web/consulta/` funciona tanto si Railway
toma el `railway.json` de esa carpeta como si toma el de la raíz.

**Alternatives considered**: Render Static Sites o Vercel (gratuitos y no consumen crédito, pero no
se pueden apagar de forma remota con un solo paso sin perder la configuración; siguen siendo válidos si
se prioriza el costo cero); una sola dirección con la clave en la URL (la clave quedaría en el historial
y en los registros del servidor); una sola dirección con selector de instancia (mezcla las claves de
dos unidades en el mismo navegador); App Sleeping de Railway (el sitio se despierta con cualquier
visita, no es un interruptor).

## 12. Retiro del cliente anterior

**Decision**: se eliminan `web/index.html`, `web/src/`, `web/package.json`, `web/package-lock.json`,
`web/tsconfig.json`, `web/vite.config.ts` y `web/README.md`. `web/` queda como carpeta de los dos
artefactos (`web/admin/`, `web/consulta/`) con un `web/README.md` breve que los presenta. La
Consulta usa el puerto 3000 de desarrollo, el que usaba el cliente anterior.

**Rationale**: aclaración del 2026-10-08 (se elimina en esta entrega). Las referencias al cliente anterior en `README.md`, `docs/OPERACION.md`,
`docs/ARQUITECTURA.md`, `docs/PRUEBAS_MVP.md` y `docs/ESCALABILIDAD.md` se actualizan en la misma
entrega (en ESCALABILIDAD solo donde describe el estado actual, no el histórico).
