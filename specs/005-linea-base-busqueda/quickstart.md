# Quickstart: medir la línea base de la búsqueda

Guía para validar la feature de punta a punta. Detalle de comandos en [contracts/linea-base-cli.md](contracts/linea-base-cli.md) y de formatos en [data-model.md](data-model.md). Se mide contra producción (la información se considera pública para pruebas).

## Requisitos

1. Entorno del proyecto: `source .venv/bin/activate && pip install -e ".[dev]"`.
2. `.env.produccion` (ignorado por git, ver [OPERACION.md](../../docs/OPERACION.md#cargar-documentos-ingesta)) con `DATABASE_URL` (Neon), `QDRANT_URL`, `QDRANT_API_KEY`, `QDRANT_COLLECTION` y `EMBEDDING_PROVIDER=local`.
3. Para `respuestas`: la clave de un artefacto con acceso a los dos programas (idealmente uno propio de pruebas con tope diario bajo), la clave de administración para leer los costos y la API de Railway encendida (`python scripts/servicios.py encender MIA`, solo cuando se vaya a medir).

## 1. Puntajes (sin gasto de modelo)

```bash
python scripts/linea_base.py puntajes --etiqueta base --env-file .env.produccion
```

Debe terminar en menos de 10 minutos, sin tokens, y mostrar por caso los puntajes ordenados, cuáles superan el umbral, la ventana de separación y el barrido de umbrales. Repetir con otra etiqueta y comparar:

```bash
python scripts/linea_base.py puntajes --etiqueta base-2 --env-file .env.produccion
python scripts/linea_base.py comparar base base-2   # debe dar 0 diferencias (SC-007)
```

## 2. Respuestas completas (con gasto)

Con un tope fijado antes:

```bash
python scripts/linea_base.py respuestas --etiqueta base --url https://mia-main.up.railway.app \
  --clave "$MIA_ARTIFACT_KEY" --clave-admin "$ADMIN_KEY" --tope-usd 0.50 --modo ambos
```

Primero con `--solo S22-1,A1,N1` para ver el costo de pocos casos. El gasto total debe quedar bajo el tope y coincidir con el módulo Uso.

## 3. Informe

```bash
python scripts/linea_base.py informe base --salida docs/LINEA_BASE_BUSQUEDA.md
```

## Comprobaciones de aceptación

- Ningún archivo de `tmp/linea_base/` ni el informe contiene texto de fragmentos o de respuestas (revisar una muestra, SC-004).
- `git status` tras las corridas: solo cambian `scripts/`, `tests/`, `specs/` y `docs/`; nada en `src/` ni migraciones (FR-016).
- La medición de puntajes no escribió nada: el conteo de fragmentos por dominio de la corrida coincide con el de antes y después.
- `pytest tests/unit/test_linea_base.py` y `ruff check scripts tests` pasan.
