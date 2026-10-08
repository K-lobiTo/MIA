# Research: Panel de administración de MIA

Decisiones técnicas de la feature 002. Cada una resuelve una incógnita del contexto técnico de
[plan.md](plan.md). Verificado el 2026-10-08.

## 1. Migraciones del esquema existente

**Decision**: Alembic, con migraciones en `src/mia/storage/migrations/`, `render_as_batch=True` (para
que los cambios de restricciones funcionen también en SQLite) y dos revisiones:

1. `0001_esquema_inicial`: el esquema actual (`domains`, `documents`) tal como lo crea hoy
   `create_all`.
2. `0002_panel_administracion`: tablas nuevas (`units`, `folders`, `artifacts`, `artifact_units`,
   `artifact_domains`, `queries`) y cambios en las existentes (`domains.unit_id`, unicidad de
   `domains.name` por unidad, `documents.folder_id`).

`init_db()` deja de usar `create_all` y aplica `alembic upgrade head` al arrancar la API. Si la base
ya tiene tablas pero no la tabla `alembic_version` (Neon y las SQLite locales de hoy), primero la marca
en `0001` (`stamp`) y después aplica el resto. Los tests siguen creando su base con `create_all` sobre
los modelos, que son la misma fuente que las migraciones.

**Rationale**: la base de Neon ya existe y tiene datos reales; Alembic es la herramienta estándar con
SQLAlchemy y ya estaba prevista en [ESCALABILIDAD.md](../../docs/ESCALABILIDAD.md). Aplicar las
migraciones al arrancar evita un paso manual en Railway (una sola instancia, sin riesgo de dos
migraciones a la vez). El `stamp` automático evita tener que entrar a Neon a marcar la base a mano.

**Alternatives considered**:
- Seguir con `create_all` y agregar columnas con `ALTER TABLE` a mano: no deja registro de qué cambios
  tiene cada base y se repetiría en cada versión.
- Comando de pre-deploy en Railway (`alembic upgrade head`): equivalente, pero suma configuración fuera
  del repositorio; se puede adoptar más adelante sin cambiar las migraciones.

## 2. `domains.unit_id` nullable

**Decision**: la columna `unit_id` de `domains` es nullable en la base. La API exige la unidad al crear
un dominio, y el inventario agrupa los dominios sin unidad bajo "Sin unidad".

**Rationale**: la migración `0002` es solo de esquema y corre al arrancar en producción, antes de la
reorganización de datos (decisión 9). Con la columna obligatoria, la migración fallaría sobre los cinco
dominios actuales o tendría que inventarles una unidad.

**Alternatives considered**: hacer la reorganización dentro de la migración. Rechazado porque necesita
los archivos de `tmp/` (que no están en el servidor) y actualizar Qdrant, que no es parte del esquema.

## 3. Claves de acceso

**Decision**:
- **Administración**: variable de entorno `ADMIN_KEY`, enviada en el encabezado `X-Admin-Key` y
  comparada con `hmac.compare_digest`. Sin `ADMIN_KEY` configurada, las operaciones de administración
  responden 503 (no quedan abiertas por olvido).
- **Artefactos**: clave generada con `secrets.token_urlsafe(32)` con el prefijo `mia_`, enviada en el
  encabezado `X-Artifact-Key`. Se guarda su SHA-256 (indexado, para buscar el artefacto por la clave) y
  sus primeros 8 caracteres para mostrar (`mia_k3f9...`).

**Rationale**: una clave aleatoria de 256 bits no se puede adivinar por fuerza bruta, así que un hash
rápido como SHA-256 basta; los hashes lentos (bcrypt, argon2) existen para contraseñas elegidas por
personas y aquí solo agregarían latencia a cada consulta. Encabezados separados evitan confundir una
clave de artefacto con la de administración.

**Alternatives considered**: `Authorization: Bearer` para ambas (obliga a distinguir el tipo de clave
por su forma); JWT (innecesario: no hay sesiones ni expiración, y revocar exige la base igual).

## 4. Lectura del inventario sin clave

**Decision**: `GET /inventory`, `GET /units` y `GET /config` responden sin clave (ADM-1: el inventario
se ve sin clave de administración). El registro de consultas, los artefactos y el módulo Uso sí exigen
la clave de administración. `GET /domains` sin clave devuelve todos los dominios como hoy; con la clave
de un artefacto, solo los permitidos.

**Rationale**: es lo que pide ADM-1 y mantiene el comportamiento actual de la API. Los nombres de
dominios y archivos no son información sensible; las preguntas registradas sí (FR-036).

**Alternatives considered**: exigir clave de administración también para ver: más seguro, pero
contradice ADM-1 y obligaría a repartir la clave a quien solo quiere mirar el inventario.

## 5. Modos de respuesta y proveedor por modo

**Decision**: la configuración de la instancia define un proveedor y un modelo por modo:
`LLM_PROVIDER_LITERAL`, `LLM_MODEL_LITERAL`, `LLM_REASONING_EFFORT_LITERAL` y lo mismo con
`_RAZONAMIENTO`, más precios de respaldo (USD por millón de tokens de entrada y de salida) por modo. Si
las variables del modo literal faltan, se usan las actuales (`LLM_PROVIDER`, `OPENROUTER_MODEL`,
`OPENROUTER_REASONING_EFFORT`), para no romper despliegues existentes. Un modo sin proveedor
configurado figura como no disponible en `/config`.

La fábrica pasa a recibir el modelo y el esfuerzo: `get_llm_provider(name, model, reasoning_effort)`
(con caché por combinación). `OpenRouterLLMProvider` usa esos parámetros; los demás proveedores ignoran
los que no aplican.

**Rationale**: mantiene el principio II (interfaz más fábrica) y el III (cualquier proveedor por modo,
también uno local). Los artefactos piden "literal" o "razonamiento" y nunca ven el modelo.

**Alternatives considered**: dos claves de OpenRouter o dos instancias de la API: más costo y
configuración sin beneficio.

## 6. Uso y costo de cada respuesta

**Decision**: `LLMProvider.answer()` pasa a devolver un `LLMAnswer` con `text`, `model`,
`prompt_tokens`, `completion_tokens`, `reasoning_tokens` y `cost_usd` (estos cuatro opcionales).
OpenRouter incluye en cada respuesta, sin pedirlo, el objeto `usage` con `prompt_tokens`,
`completion_tokens`, `completion_tokens_details.reasoning_tokens` y `cost` (USD). Si un proveedor no
informa el costo, se estima con los tokens y los precios de respaldo del modo, y la consulta queda
marcada como `cost_estimated`.

**Rationale**: el costo real de OpenRouter es el que importa para los topes y para coincidir con su
panel (SC-007). Ver [Usage Accounting](https://openrouter.ai/docs/use-cases/usage-accounting): el
parámetro `usage: {include: true}` ya no tiene efecto porque el uso viene siempre.

**Alternatives considered**: calcular siempre con precios configurados (se desactualiza y no refleja
caché ni razonamiento); consultar `/api/v1/generation` después de cada respuesta (una llamada extra por
consulta).

## 7. Saldo de OpenRouter

**Decision**: `GET /usage/balance` consulta `GET https://openrouter.ai/api/v1/key` con la clave normal
de MIA y usa `limit_remaining`: lo que le queda al **límite de crédito de la clave** (la clave
`mia-railway` tiene un límite de 30 USD). El panel lo muestra con ese nombre ("Límite restante de la
clave de MIA") y una nota: el saldo de la cuenta puede ser menor, y MIA deja de responder con el menor
de los dos. Si además hay una clave de gestión configurada (`OPENROUTER_MANAGEMENT_KEY`, opcional), se
lee también `GET /api/v1/credits` (`total_credits - total_usage`, saldo de toda la cuenta) y se muestra
el menor de los dos valores, indicando cuál limita. Sin límite en la clave ni clave de gestión, responde
"no disponible" con el motivo (caso borde del spec).

**Rationale**: `/credits` exige una clave de gestión (403 con la clave normal), que opera a nivel de
cuenta y puede crear claves de inferencia sin límite: si se filtrara desde el servidor, el daño posible
pasa de "el límite de la clave" a "todo el saldo de la cuenta". Por eso no se recomienda configurarla
en producción. La práctica recomendada para el prototipo es ajustar el límite de la clave de MIA al
saldo cargado, así `limit_remaining` coincide con lo que realmente queda.
Fuentes: [Get current API key](https://openrouter.ai/docs/api/api-reference/api-keys/get-current-api-key),
[Get credits](https://openrouter.ai/docs/api-reference/get-credits).

**Alternatives considered**: clave de gestión obligatoria (más exactitud a cambio de más riesgo);
cargar el saldo de la cuenta a mano en el panel (se desactualiza).

## 8. Topes y día de corte

**Decision**: el día de los topes se calcula en la zona `America/Costa_Rica` con `zoneinfo`; se agrega
la dependencia `tzdata` porque la imagen `python:3.12-slim` no trae la base de zonas horarias. Antes de
cada consulta se suman con una sola consulta SQL los costos del día del artefacto (total y del modo con
razonamiento) y de toda la API, sobre la tabla `queries` con índice `(artifact_id, created_at)`. Las
fechas se guardan en UTC.

**Rationale**: la suma sobre el registro es la misma fuente que usa el módulo Uso, así que el panel y
el control nunca discrepan. Con el volumen del prototipo (cientos de consultas por día) la consulta es
inmediata. El exceso por consultas simultáneas queda acotado (caso borde del spec) sin necesidad de
bloqueos.

**Alternatives considered**: contadores en memoria (se pierden al reiniciar Railway); una tabla de
acumulados por día (más escrituras y riesgo de desincronizarse del registro).

## 9. Reorganización de los datos existentes

**Decision**: script de una sola vez `scripts/reorganizar_v2.py`, con el mapeo en
`scripts/datos/reorganizacion_v2.json` (unidades, dominios destino, carpetas por ruta de origen y la
clasificación del anexo A). Usa las mismas variables de entorno que la API (como
`scripts/cargar_carpeta.py` en local contra producción). Es idempotente (busca por nombre antes de
crear), tiene `--simular` para mostrar los cambios sin aplicarlos, ubica cada documento por su nombre
de archivo dentro de la carpeta de origen, y para los documentos que cambian de dominio actualiza
Qdrant con `set_payload` filtrando por `document_id`. Al terminar muestra un resumen comparable con la
tabla de la sección 2.3.

**Rationale**: los archivos de origen están en la laptop (`tmp/`), igual que la ingesta local de hoy
(ver memoria del proyecto: la ingesta se hace en local). Con `--simular` y una prueba contra una base
local primero, se cumple FR-017.

**Alternatives considered**: hacerlo desde el panel (no tiene acceso a las rutas de origen ni sentido
como función permanente); dentro de una migración (ver decisión 2).

## 10. Agregaciones del módulo Uso

**Decision**: `/usage` lee las consultas del período (y del período anterior, para la comparación) con
SQL filtrado por fechas, artefacto y modo, y calcula los indicadores, percentiles y series en Python.

**Rationale**: SQLite (desarrollo y tests) no tiene funciones de percentil, y con el volumen del
prototipo (miles de filas por mes) agregar en Python es inmediato y portable entre SQLite y Postgres.

**Alternatives considered**: agregaciones en SQL con funciones de Postgres (`percentile_cont`): rompe
los tests en SQLite; tablas resumen por día: innecesarias a esta escala (se pueden agregar después).

## 11. Frontend del panel

**Decision**: React 19 + TypeScript + Vite en `web/admin/`, con:
- **TanStack Query** para pedidos, caché y el sondeo del estado de documentos en proceso (INV-5).
- **React Router** con `HashRouter` (un módulo por ruta: `#/inventario`, `#/artefactos`, `#/uso`),
  que funciona en un sitio estático sin configurar reescrituras.
- **Recharts** para la gráfica de barras apiladas de Uso.
- CSS propio con variables (modo claro y oscuro con `prefers-color-scheme`), sin biblioteca de
  componentes.
- Proxy de Vite en desarrollo (como `web/`), y CORS en la API para publicar como sitio estático.

El cliente de la API vive en `web/admin/src/api/`; se extrae a un paquete compartido cuando se
construya la Consulta administrativa (no antes, para no diseñar en abstracto).

**Rationale**: es el stack elegido en el documento de requerimientos (sección 1). TanStack Query
resuelve sondeo, invalidación tras crear o subir, y estados de carga y error con poco código propio.

**Alternatives considered**: `fetch` con `useEffect` (más código propio para sondeo e invalidación);
una biblioteca de componentes (MUI, Mantine): más peso del necesario para tres módulos.

## 12. CORS

**Decision**: `CORSMiddleware` con los orígenes de la variable `CORS_ORIGINS` (lista separada por comas,
vacía por defecto), permitiendo los encabezados `X-Admin-Key` y `X-Artifact-Key`.

**Rationale**: FR-027; vacía por defecto mantiene el comportamiento actual hasta publicar los sitios.

## 13. Pruebas

**Decision**: pytest con `TestClient` para cada ruta nueva o modificada (FR-037), con proveedores
falsos como en los tests actuales; pruebas de la reorganización sobre una base SQLite y un `VectorStore`
falso; `tsc` y `vite build` del panel, y Vitest solo para funciones puras del frontend (filtro del
árbol, cálculo de "consultas que alcanza el tope"). `scripts/pruebas_mvp.py` recibe `--clave` y usa los
nombres de dominio nuevos (FR-038).

**Rationale**: la lógica que puede romper datos o permisos está en la API, donde ya hay infraestructura
de pruebas; el frontend se valida con la guía de [quickstart.md](quickstart.md).
