# Contrato: `scripts/linea_base.py`

Herramienta de línea de comandos. No expone nada en la API de MIA. Todas las salidas por consola y por archivo cumplen FR-006 (sin texto de fragmentos ni de respuestas ni nombres reales).

```text
python scripts/linea_base.py puntajes   --etiqueta E [--env-file F] [--solo ID,ID] [--confirmo-produccion]
python scripts/linea_base.py respuestas --etiqueta E --url URL --clave K --tope-usd N [--clave-admin A] [--modo literal|razonamiento|ambos] [--solo ID,ID] [--confirmo-produccion]
python scripts/linea_base.py informe    ETIQUETA [--salida docs/LINEA_BASE_BUSQUEDA.md]
python scripts/linea_base.py comparar   ETIQUETA_A ETIQUETA_B
```

## `puntajes`

- Carga `--env-file` (formato de `uvicorn --env-file`, tiene prioridad sobre `.env`) antes de importar `mia`.
- Sale con error, sin consultar, si: el destino es remoto y falta `--confirmo-produccion`; la dimensión de la colección no coincide con la del proveedor de embeddings; no hay casos para correr.
- Solo ejecuta lecturas (SELECT, `query_points`, `count`, `get_collection`).
- Escribe `tmp/linea_base/<fecha>-<etiqueta>/puntajes.json` (corrida, mediciones y resumen) y un resumen por consola con ids, puntajes y alias.
- No usa tokens de ningún proveedor de modelos.
- Código de salida 0 aunque algún caso "falle": medir no es aprobar. 2 si no pudo medir.

## `respuestas`

- `--tope-usd` es obligatorio; imprime el número de consultas previstas y empieza. Se detiene al alcanzar el tope y escribe el informe parcial con `parcial: true`.
- `--clave` es la del artefacto (o `MIA_ARTIFACT_KEY`); `--clave-admin` (o `MIA_ADMIN_KEY`) permite leer el costo; sin ella el costo queda `null` y se avisa.
- Reintenta 502 hasta 3 veces; si persiste, el caso queda `no_concluyente`.
- Escribe `respuestas.json` en la misma carpeta de la etiqueta.
- Código de salida 0, o 2 si no pudo correr.

## `informe`

- Lee los dos archivos de la etiqueta y escribe Markdown con alias de documentos.
- Aborta sin escribir si en el texto aparece un valor de `tmp/nombres_casos.json` o un nombre de archivo de los documentos.

## `comparar`

- Imprime, por caso, cambios de resultado, de mejor puntaje (diferencia mayor a 0,001) y de fuentes; avisa si el conteo de fragmentos por dominio difiere entre corridas.

## Archivos

| Archivo | Versionado | Contenido |
|---|---|---|
| `scripts/datos/casos_busqueda.json` | sí | Casos (ver [data-model.md](../data-model.md)). |
| `tmp/nombres_casos.json` | no | Valores de los marcadores `{{clave}}`. |
| `tmp/linea_base/<fecha>-<etiqueta>/*.json` | no | Salida cruda con nombres de archivo. |
| `docs/LINEA_BASE_BUSQUEDA.md` | sí | Informe anonimizado. |
