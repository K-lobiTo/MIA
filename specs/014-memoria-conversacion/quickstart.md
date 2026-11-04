# Quickstart: validar la memoria de conversación

De lo más barato (pruebas automáticas) a lo real (producción, solo con tu autorización). Diseño en [research.md](research.md), [data-model.md](data-model.md) y [contracts/](contracts/). Todo el desarrollo se hace en `dev`.

## 0. Prerrequisitos

```bash
source .venv/bin/activate && pip install -e ".[dev]" && pip install -e "./whatsapp[dev]"
docker compose up -d qdrant                      # Qdrant local (para la medición del paso 2)
cd web/admin && npm ci && cd ../consulta && npm ci && cd ../..
```

## 1. Pruebas automáticas (sin red, sin cuota)

```bash
pytest tests/unit/test_history.py tests/unit/test_followup.py tests/unit/test_query_history.py
pytest tests/unit/test_artifacts_memory.py tests/unit/test_bots_memory.py tests/unit/test_migrations.py
pytest whatsapp/tests/test_context.py whatsapp/tests/test_flow_clarify.py whatsapp/tests/test_api_client.py
pytest && ruff check src tests scripts whatsapp
cd web/admin && npm run typecheck && npm test && npm run build
cd ../consulta && npm run typecheck && npm test && npm run build
```

Lo que deben demostrar:
- **Historial**: con `context_turns = 0` se ignora por completo (mismo resultado, mismas llamadas al almacén y al modelo, mismo costo); con N se usan solo las últimas N vueltas; un campo `role` o más de 50 vueltas dan 422; se descartan las vueltas "sin información"; los recortes por vuelta, total y modo; el historial no queda en la base ni en Uso.
- **Modelo**: el bloque "Conversación anterior" va rotulado y antes del contexto, la instrucción de sistema trae el párrafo de que no es fuente, las respuestas de razonamiento llevan su advertencia y las cuatro proveedores implementados arman el mismo mensaje.
- **Reformulación**: solo se reformula un seguimiento; `rules` junta las dos preguntas anteriores con la actual, `model` reescribe con una llamada corta (con su costo en el registro) y cae a `rules` si falla, `off` no reformula; una pregunta que se entiende sola no cambia.
- **Artefactos y bots**: rango 0 a 10 (artefacto) y 1 a 10 o nulo (bot), alcance, línea de registro con el valor anterior y el nuevo, `context_turns` en `/config`, y la migración `0008` con su `downgrade`.
- **Servicio**: el límite de la ventana sale de `/bot/messages` (y respalda en `BOT_CONTEXT_MESSAGES`), un cambio rige en el mensaje siguiente y el bot no recibe historial al modelo.
- **Consulta**: envía las últimas N vueltas respondidas (ni las fallidas ni las "sin información"), nada con 0, y muestra el aviso.
- **Sin regresiones**: las pruebas existentes pasan (con memoria 0) y la batería del MVP da 19 de 19.

## 2. Medir las dos estrategias de reformulación (research R9)

Con los seis documentos de los posgrados (`tmp/nuevos/`, o una carpeta equivalente) y un Qdrant local:

```bash
python scripts/medir_memoria.py --documentos tmp/nuevos --sin-modelo      # off y rules, sin gasto
python scripts/medir_memoria.py --documentos tmp/nuevos                    # además model: llama a OpenRouter (centavos, con tu autorización)
```

El script recorre `scripts/datos/casos_memoria.json` (conversaciones con un seguimiento final: `tema_anterior`, `pronombre`, `cambio_de_modo` y `calculo_en_razonamiento`) y reporta por estrategia cuántos seguimientos recuperan el documento esperado, el costo y el tiempo. Con ese resultado se fija `HISTORY_REFORMULATION` por defecto y se anota en research R9. El criterio de éxito es SC-001 (al menos 80 % de los seguimientos con la estrategia elegida).

## 3. Recorrer la Consulta en la laptop

```bash
ADMIN_KEY=admin-local QUERY_CITED_SOURCES=on uvicorn mia.api.main:app --reload
cd web/consulta && MIA_API_URL=http://localhost:8000 npm run dev      # y la clave de un artefacto
```

1. En el panel (`web/admin`), poner la **Memoria de conversación** del artefacto en 3.
2. En la Consulta: preguntar "¿Cuándo empiezan las lecciones de la maestría en analítica de negocio?" y luego "¿y cuánto cuesta?": responde el costo de Analítica con su fuente, y la Consulta muestra "Recuerda las últimas 3 preguntas".
3. Pedir en modo con razonamiento un cálculo ("¿Cuántos créditos suman los bloques 1 a 3?") y luego, en modo literal, "¿y cuántos son en total?": la respuesta literal no presenta el total como dato de un documento.
4. Recargar la página: la conversación empieza de cero. Poner la memoria en 0: el seguimiento vuelve a no entenderse, sin reiniciar nada.
5. En el módulo Bots, cambiar la memoria del bot de 2 a 4 y comprobar en los registros del servicio que sigue respondiendo; sin tocar variables.

## 4. Medir el costo (SC-007)

Con la misma serie de 6 preguntas de seguimiento, en un artefacto con memoria 0 y luego con memoria 4, comparar el costo medio por consulta en el módulo Uso del panel. Anotar el aumento en research R9.

## 5. Producción (solo con tu autorización)

1. Merge de `dev` a `main` y `git push origin main`.
2. Desplegar `MIA`, `mia-whatsapp`, `mia-panel` y `mia-computacion` (la Consulta); la API migra a la `0008` al arrancar (sin riesgo: columnas con valor por defecto). No cambia nada mientras la memoria de todos los artefactos esté en 0.
3. En el panel, poner la memoria del artefacto de la Consulta (por ejemplo, 3) y probar los pasos 2 y 3 del apartado anterior contra producción.

**Volver atrás**: poner la memoria del artefacto en 0 (rige en la consulta siguiente). Para quitar las columnas: `alembic downgrade 0007` **antes** de desplegar una versión anterior de la API (OPERACION.md, "Desplegar cambios"); solo se pierden los dos números.
