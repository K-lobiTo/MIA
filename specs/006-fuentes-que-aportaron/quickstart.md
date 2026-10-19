# Quickstart: validar que las fuentes sean las que aportaron

Guía para validar la feature de punta a punta. Contratos en [contracts/citas-y-fuentes.md](contracts/citas-y-fuentes.md) y estructuras en [data-model.md](data-model.md). La referencia de comparación es la corrida `base` de la feature 005 ([LINEA_BASE_BUSQUEDA.md](../../docs/LINEA_BASE_BUSQUEDA.md)).

## 1. Pruebas automáticas (sin red)

```bash
source .venv/bin/activate
pytest tests/unit/test_citations.py tests/unit/test_query_citations.py tests/unit/test_query_sources.py tests/unit/test_query_no_info.py
pytest                    # toda la suite
ruff check src tests scripts
```

Deben pasar: el parseo y la validación (todas las filas de la tabla del contrato), la ruta con la opción apagada (respuesta idéntica a la de antes, incluida la etiqueta del contexto), encendida con citas válidas, parciales, inválidas, repetidas y sin línea, y "sin información" con y sin línea de citas.

## 2. Control con la opción apagada (SC-008 y ruido de la medición)

Con el código nuevo y `QUERY_CITED_SOURCES` en `off`, correr `respuestas --etiqueta control` (mismo comando que el paso siguiente) y comparar con `base`: la lista de documentos mostrados por caso debe ser la misma (SC-008). Esta corrida también mide el ruido entre corridas de costo y latencia, que sirve para leer SC-004 y SC-005.

## 3. Con la opción encendida (SC-001 a SC-007)

Requisitos: `.env` con `MIA_ARTIFACT_KEY` (artefacto de prueba con acceso a los dos programas, que se activa solo para medir) y `MIA_ADMIN_KEY`, y un tope de gasto fijado antes.

```bash
# 1. Encender la opción y la API (solo para medir)
railway variable set QUERY_CITED_SOURCES=on -s MIA --skip-deploys
python scripts/servicios.py encender MIA --forzar --ref origin/dev   # la rama con la feature; sin --ref se despliega main
# Importante: cambiar la variable SIN --skip-deploys redespliega desde main y se pierde el código de dev (ver OPERACION.md)
# 2. Medir los 32 casos en los dos modos (después del control del paso 2)
python scripts/linea_base.py respuestas --etiqueta citas --url https://mia-main.up.railway.app --tope-usd 0.40
# 3. Comparar con la línea base y con el control
python scripts/linea_base.py comparar base control
python scripts/linea_base.py comparar control citas
python scripts/linea_base.py comparar base citas
python scripts/linea_base.py informe citas --salida tmp/linea_base/informe-citas.md   # no sobrescribir docs/LINEA_BASE_BUSQUEDA.md
# 4. Volver a apagar
railway variable set QUERY_CITED_SOURCES=off -s MIA --skip-deploys
python scripts/servicios.py apagar MIA --forzar
```

Qué leer: fuentes sobrantes por modo (meta: bajar al menos 50 %), casos que cambian de resultado (ninguno de los 19 de la batería), costo medio y latencia p50 frente a la línea base (+5 % y +10 % como máximo), la mediana de la razón de costo y de latencia caso por caso frente a `base` y `control` (el ruido entre ambos da el margen real de SC-004 y SC-005), proporción de respuestas donde rigió la regla de seguridad (10 % como máximo) y que ninguna respuesta con contenido quedó sin fuentes.

## 4. Si algo sale mal

Volver a `QUERY_CITED_SOURCES=off` y reiniciar el servicio devuelve el comportamiento anterior. Como no hay migraciones, volver al tag `prototipo-v2-estable` también es seguro.

## Comprobaciones de aceptación

- `git diff --stat main..dev -- alembic src/mia/storage/migrations` no muestra cambios (sin migraciones).
- La respuesta de `POST /query` conserva sus campos (la Consulta y `scripts/pruebas_mvp.py` siguen funcionando sin cambios).
- Ninguna salida de la herramienta contiene el texto de las respuestas ni de los fragmentos.
