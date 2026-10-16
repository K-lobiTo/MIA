# Contrato: `scripts/linea_base.py`

Herramienta de línea de comandos. No expone nada en la API de MIA. Todas las salidas por consola y por archivo cumplen FR-006 (sin texto de fragmentos ni de respuestas).

```text
python scripts/linea_base.py inventario [--env-file F]
python scripts/linea_base.py puntajes   --etiqueta E [--env-file F] [--solo ID,ID] [--casos RUTA]
python scripts/linea_base.py respuestas --etiqueta E --url URL --clave K --tope-usd N [--clave-admin A] [--modo literal|razonamiento|ambos] [--solo ID,ID] [--casos RUTA]
python scripts/linea_base.py informe    ETIQUETA [--salida docs/LINEA_BASE_BUSQUEDA.md]
python scripts/linea_base.py comparar   ETIQUETA_A ETIQUETA_B
```

## Opciones comunes

- `--casos RUTA` (en `puntajes` y `respuestas`): usa un archivo de casos distinto de `scripts/datos/casos_busqueda.json`, con el mismo formato. Sirve para probar borradores de casos sin tocar el archivo versionado.
- Código de salida: `0` si midió, `2` si no pudo medir (archivo de entorno ilegible, dimensión incompatible, falta de clave o de tope, API apagada o clave inválida, ningún caso para correr). En esos casos no se escribe ningún archivo. `comparar` devuelve además `1` si hay diferencias.
- `respuestas` se detiene, con informe parcial, ante un 429 (tope diario del artefacto) y ante un 401 o 403 (clave inválida o artefacto desactivado).

## `inventario`

- Solo lectura. Lista cada `Programa / Dominio` con cantidad de documentos y fragmentos y los nombres de archivo de los documentos. No guarda nada.

## `puntajes`

- Carga `--env-file` (formato de `uvicorn --env-file`, tiene prioridad sobre `.env`) antes de importar `mia`.
- Sale con error, sin consultar, si: la dimensión de la colección no coincide con la del proveedor de embeddings; no hay casos para correr.
- Solo ejecuta lecturas (SELECT, `query_points`, `count`, `get_collection`); un guardia en el código impide cualquier otra operación.
- Escribe `tmp/linea_base/<fecha>-<etiqueta>/puntajes.json` (corrida, mediciones y resumen) y un resumen por consola con ids, puntajes y nombres de documento.
- No usa tokens de ningún proveedor de modelos.
- Código de salida 0 aunque algún caso "falle": medir no es aprobar. 2 si no pudo medir.

## `respuestas`

- `--tope-usd` es obligatorio; imprime el número de consultas previstas y empieza. Se detiene al alcanzar el tope y escribe el informe parcial con `parcial: true`.
- Lee `.env` por sí mismo: `MIA_ARTIFACT_KEY` (o `--clave`) y `MIA_ADMIN_KEY` (o `--clave-admin`), que permite leer el costo; sin ella el costo queda `null` y se avisa. Omite con aviso los casos cuyos dominios el artefacto no puede consultar y se detiene ante un 429 de tope diario.
- Reintenta 502 hasta 3 veces; si persiste, el caso queda `no_concluyente`.
- Escribe `respuestas.json` en la misma carpeta de la etiqueta.
- Código de salida 0, o 2 si no pudo correr.

## `informe`

- Lee los archivos de la etiqueta (`puntajes.json` y `respuestas.json` pueden estar en corridas distintas: toma la más reciente de cada uno) y escribe el Markdown del informe (contexto, tabla por caso, resúmenes, ventana de separación y casos omitidos).
- Si el archivo de salida ya existe y tiene una sección `## Lectura` escrita a mano, la conserva al regenerar.

## `comparar`

- Imprime, por caso, cambios de resultado, de mejor puntaje (diferencia mayor a 0,001) y de fuentes; avisa si el conteo de fragmentos por dominio difiere entre corridas.

## Archivos

| Archivo | Versionado | Contenido |
|---|---|---|
| `scripts/datos/casos_busqueda.json` | sí | Casos (ver [data-model.md](../data-model.md)). |
| `tmp/linea_base/<fecha>-<etiqueta>/*.json` | no | Salida cruda de cada corrida. |
| `docs/LINEA_BASE_BUSQUEDA.md` | sí | Informe de la línea base. |

## Ampliación de la feature 006

- `respuestas` registra por consulta `regla_de_seguridad` (verdadero si el detalle de Uso trae la nota `Fuentes: sin citas utilizables...`, falso si no, nulo si no se pudo leer el detalle) y el resumen por modo suma `regla_de_seguridad_aplicada` y `proporcion_regla_de_seguridad` sobre las respuestas con contenido.
- `comparar` muestra las diferencias de `regla_de_seguridad` y, cuando ambas corridas tienen `respuestas`, la **mediana de la razón (B sobre A) de costo y de latencia caso por caso** por modo. `informe` muestra la regla de seguridad en la sección de cada modo.
- Las corridas anteriores a la 006 (sin `regla_de_seguridad`) se leen sin error.
