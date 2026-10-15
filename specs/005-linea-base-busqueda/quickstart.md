# Quickstart: medir la línea base de la búsqueda

Guía para validar la feature de punta a punta. Detalle de comandos en [contracts/linea-base-cli.md](contracts/linea-base-cli.md) y de formatos en [data-model.md](data-model.md).

## Requisitos

1. Entorno del proyecto: `source .venv/bin/activate && pip install -e ".[dev]"`.
2. Qdrant local y una copia de los datos:
   ```bash
   docker compose up -d qdrant
   # API local con ingesta (procedimiento de docs/OPERACION.md, "Cargar documentos"),
   # DATABASE_URL local, QDRANT_URL=http://localhost:6333 y los archivos de tmp/
   INGESTION_SYNC=true uvicorn mia.api.main:app --port 8010
   python scripts/cargar_carpeta.py --url http://localhost:8010 --clave "$ADMIN_KEY" ...   # una vez por dominio
   ```
3. Valores reales de los marcadores de los casos, solo en local: `tmp/nombres_casos.json` (`{"clave": "valor"}`). Sin este archivo se omiten esos casos.

## 1. Puntajes (sin gasto)

```bash
python scripts/linea_base.py puntajes --etiqueta base-local
```

Debe terminar en menos de 10 minutos, sin tokens, y mostrar por caso los puntajes ordenados, cuáles superan el umbral, la ventana de separación y el barrido de umbrales. Repetir con otra etiqueta y comparar:

```bash
python scripts/linea_base.py puntajes --etiqueta base-local-2
python scripts/linea_base.py comparar base-local base-local-2   # debe dar 0 diferencias (SC-007)
```

## 2. Respuestas completas (con gasto)

Con la API local o la de producción en marcha, y un tope fijado antes:

```bash
python scripts/linea_base.py respuestas --etiqueta base-local --url http://localhost:8010 \
  --clave "$MIA_ARTIFACT_KEY" --clave-admin "$ADMIN_KEY" --tope-usd 0.50 --modo ambos
```

Primero con `--solo S22-1,A1,N1` para ver el costo de pocos casos. El gasto total debe quedar bajo el tope y coincidir con el módulo Uso.

## 3. Confirmar en producción (opcional, con autorización por corrida)

```bash
python scripts/linea_base.py puntajes --etiqueta base-prod --env-file .env.produccion --confirmo-produccion
python scripts/linea_base.py comparar base-local base-prod
```

## 4. Informe

```bash
python scripts/linea_base.py informe base-local --salida docs/LINEA_BASE_BUSQUEDA.md
```

## Comprobaciones de aceptación

- Buscar en lo versionado nombres reales y texto de fragmentos (por ejemplo, cada valor de `tmp/nombres_casos.json` con `grep -rF`): no debe haber resultados (SC-004).
- `git status` tras las corridas: solo cambian `scripts/`, `tests/`, `specs/` y `docs/`; nada en `src/` ni migraciones (FR-016).
- `pytest tests/unit/test_linea_base.py` y `ruff check scripts tests` pasan.
