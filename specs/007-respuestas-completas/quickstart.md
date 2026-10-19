# Quickstart: validar respuestas completas y sin cortes

Contratos en [contracts/contexto-completo-y-cortes.md](contracts/contexto-completo-y-cortes.md) y estructuras en [data-model.md](data-model.md). Referencias de comparación: la corrida `base` de la feature 005 y el `control` de la 006 ([LINEA_BASE_BUSQUEDA.md](../../docs/LINEA_BASE_BUSQUEDA.md)).

## 1. Pruebas automáticas (sin red)

```bash
source .venv/bin/activate
pytest tests/unit/test_completeness.py tests/unit/test_context.py tests/unit/test_query_completeness.py tests/unit/test_query_citations.py
pytest                    # toda la suite
ruff check src tests scripts
```

Deben pasar: las variables y sus valores inválidos, la ampliación del contexto (documento completo, avance hacia adelante, documentos secundarios sin cambio, tope de caracteres, marca de continuación), el motivo de fin por proveedor, el reintento (con tope de gasto, con "sin información", con fallo del segundo intento), el aviso, la combinación con las citas de la 006 y el comportamiento idéntico con todo apagado.

## 2. Casos de listas largas

Los casos `lista_larga` ya están en `scripts/datos/casos_busqueda.json` (último ítem esperado en `contiene`). Antes de medir, comprobar a mano que cada último ítem es el del documento.

## 3. Mediciones en producción (con autorización y tope de gasto)

Requisitos: `.env` con `MIA_ARTIFACT_KEY` (artefacto de prueba con acceso a los dos programas, activo solo mientras se mide) y `MIA_ADMIN_KEY`.

```bash
# Control: todo apagado, código de dev
railway variable set QUERY_COMPLETE_CONTEXT=off QUERY_RETRY_CUT_ANSWERS=off -s MIA --skip-deploys
python scripts/servicios.py encender MIA --forzar --ref origin/dev
python scripts/linea_base.py respuestas --etiqueta control7 --url https://mia-main.up.railway.app --tope-usd 0.40

# Contexto completo
railway variable set QUERY_COMPLETE_CONTEXT=on -s MIA --skip-deploys
python scripts/servicios.py encender MIA --forzar --ref origin/dev
python scripts/linea_base.py respuestas --etiqueta completo --url https://mia-main.up.railway.app --tope-usd 0.40

# Contexto completo y reintento
railway variable set QUERY_RETRY_CUT_ANSWERS=on -s MIA --skip-deploys
python scripts/servicios.py encender MIA --forzar --ref origin/dev
python scripts/linea_base.py respuestas --etiqueta completo-reintento --url https://mia-main.up.railway.app --tope-usd 0.40

# Comparar
python scripts/linea_base.py comparar control7 completo
python scripts/linea_base.py comparar control7 completo-reintento
python scripts/linea_base.py informe completo-reintento --salida tmp/linea_base/informe-completo.md
```

Cambiar una variable sin `--skip-deploys` redesplegaría desde `main` y se perdería el código de `dev` (ver OPERACION.md). Después del cambio se vuelve a desplegar con `encender --ref origin/dev`, que lee las variables al arrancar.

Qué leer: listas completas (SC-001), respuestas cortadas sin aviso (SC-002), los 19 casos de la batería (SC-003), proporción de reintentos (SC-004), medianas de razón de costo y de latencia contra el control (SC-005 y SC-006), la lista de fuentes con todo apagado (SC-007) y la regla de seguridad de las citas con la 006 encendida (SC-008).

## 4. Si algo sale mal

Cada variable en `off` y reiniciar el servicio devuelve el comportamiento anterior. Como no hay migraciones, volver al tag `prototipo-v2-estable` también es seguro.

## Comprobaciones de aceptación

- `git diff --stat main..dev -- src/mia/storage/migrations alembic` sin cambios.
- La respuesta de `POST /query` conserva sus campos.
- Ninguna salida de la herramienta contiene el texto de las respuestas ni de los fragmentos.
- Al terminar: variables, artefacto de prueba y API en el estado acordado, y la clave regenerada si se expuso.
