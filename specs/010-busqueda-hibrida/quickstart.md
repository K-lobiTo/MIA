# Quickstart: validar la búsqueda híbrida

Guía para comprobar la feature de punta a punta. Detalles de diseño en [research.md](research.md), [data-model.md](data-model.md) y [contracts/](contracts/). Todo se hace en `dev`. Ninguna escritura en producción (índice de Qdrant, migración, despliegue) se ejecuta sin que el usuario la autorice.

## 0. Prerrequisitos

```bash
source .venv/bin/activate && pip install -e ".[dev]"
docker compose up -d qdrant           # Qdrant local (versión reciente: soporta el índice de texto)
```

## 1. Pruebas automáticas (sin Qdrant real ni red)

```bash
pytest tests/unit/test_lexical.py tests/unit/test_query_hybrid.py tests/unit/test_equivalences.py tests/unit/test_vector_store_text.py tests/unit/test_linea_base.py
pytest tests/unit/test_palabras_script.py tests/unit/test_copiar_coleccion.py tests/unit/test_config.py tests/unit/test_ingestion_pipeline.py tests/unit/test_probar_migracion.py
pytest tests/integration                  # contra un Qdrant local (docker compose up -d qdrant); se omite sola si no hay uno
pytest && ruff check src tests scripts
cd web/admin && npm run typecheck && npm test && npm run build
```

Totales al 2026-10-19: 988 pruebas de Python con 4 omitidas (las de `tests/integration` sin Qdrant local) y 78 del panel.

Lo que deben demostrar: la opción apagada no cambia nada (ni se consulta la tabla de equivalencias); grupos, palabras vacías, siglas con puntos y regla de la mayoría (casos de [research.md](research.md) R5: Natalia, Obando, Cubillo, Zacarías, TFG); la fusión (sin duplicados, tope de ranuras, límite del modo, lista intacta sin candidatos); la caída a significado (almacén sin métodos léxicos, error, tiempo agotado) con aviso y nota; filtro de dominio; combinación con 006 a 009; rutas `/equivalences` con permisos, validación y caché; la migración `0005` con `upgrade` y `downgrade` en SQLite.

Por archivo: `test_lexical.py` (normalización, grupos, regla de la mayoría y su proporción, fusión, notas), `test_query_hybrid.py` (la ruta: opción apagada, caídas, siglas, sin información, combinación con 006 a 009 y el arranque que asegura el índice), `test_equivalences.py` (migración, caché, rutas, permisos y validación), `test_vector_store_text.py` (filtros del almacén con un cliente simulado), `test_palabras_script.py` (estado, preparar y quitar el índice), `test_copiar_coleccion.py` (copia en solo lectura del origen), `test_config.py` (valores por defecto y rangos de `HYBRID_*`), `test_ingestion_pipeline.py` (la reingesta solo usa el `upsert`), `test_probar_migracion.py` (la ida y vuelta de la migración, por defecto hasta `0004`), `test_linea_base.py` (la medición léxica, la comparación y el registro), `tests/integration/test_text_index_qdrant.py` (el índice contra un Qdrant real, incluido mover de dominio) y, en el panel, `equivalenciasUtils.test.ts` y `EquivalenciasPage.test.tsx` (la pantalla con alcance global y de programa).

## 2. Preparar un Qdrant local con el índice (gratis)

```bash
python scripts/palabras.py estado   --env-file .env      # índice ausente
python scripts/palabras.py preparar --env-file .env      # crea el índice de texto sobre text
python scripts/palabras.py estado   --env-file .env      # existe, puntos indexados = puntos
```

Con documentos de ejemplo ingeridos (`scripts/cargar_carpeta.py`) y `QUERY_HYBRID_SEARCH=on`, `uvicorn mia.api.main:app --reload`: una pregunta con un nombre pegado a un número en el documento ("Nombre Apellido2023800202") encuentra el documento.

## 3. Medición de candidatos (gratis, solo lectura)

Para calibrar sin escribir en producción, primero se copia la colección (con vectores) a un Qdrant local con el índice de texto:

```bash
python scripts/copiar_coleccion.py --origen-env .env.produccion --destino-coleccion mia_hibrida --indice
```

Y se apunta `QDRANT_COLLECTION=mia_hibrida` en el entorno local. Después:

Contra la copia local con el índice, o contra producción solo si ya tiene el índice y el usuario lo autorizó:

```bash
python scripts/linea_base.py puntajes --etiqueta hibrida --env-file .env.produccion
python scripts/linea_base.py comparar control hibrida
```

Criterios (SC-001 a SC-004): los casos objetivo (`S22-1` a `S22-4`, `SG3`, `EN1` a `EN6`, `EN10`) con su documento como candidato léxico y entre los resultados finales; ningún caso "sin información" con candidatos léxicos que lleguen al modelo (excepto los que ya llegaban, como `I1`); los 19 casos de la batería del MVP sin cambios de documento; los 12 o más casos nuevos de FR-017 calibran `HYBRID_MAX_DOCS` y `HYBRID_LEXICAL_SLOTS`.

## 4. Latencia y memoria

- **Latencia de la parte léxica**: `puntajes --palabras` guarda los milisegundos de la parte léxica por caso (`ms` en `puntajes.json`; p50 y p95 en el informe). Para la espera y fusión que evalúa SC-007 (lo que la consulta espera de más, con la búsqueda por significado en paralelo) se repitió el recorrido de los casos con `_HybridRun` de la ruta contra un Qdrant local y contra el Qdrant de producción (2026-10-19, resultados en [LINEA_BASE_BUSQUEDA.md](../../docs/LINEA_BASE_BUSQUEDA.md)); en Railway se lee del registro del servidor: `python scripts/linea_base.py registro --archivo <salida de railway logs -s MIA>`.
- **Memoria y almacenamiento**: la API no suma RAM. En Qdrant, `python scripts/palabras.py estado` (índice y fragmentos indexados) y `docker stats` del contenedor local con y sin el índice (`scripts/palabras.py quitar` y `preparar`).
- **Railway, solo con autorización**: desplegar `dev` según el flujo de [OPERACION.md](../../docs/OPERACION.md) aplica la migración `0005` a la base de Neon; tope de gasto antes de cada corrida de `respuestas` (control con `QUERY_HYBRID_SEARCH=off` y corrida con `on`), y cerrar producción al terminar como en las features 005 a 009. No se hizo en esta feature (ver tareas T058 a T061).

## 5. Panel de siglas (manual)

```bash
python scripts/idp_simulado.py                    # Microsoft simulado y API con datos de ejemplo
cd web/admin && VITE_ENTRA_CLIENT_ID=cliente-de-prueba VITE_ENTRA_AUTHORITY=https://localhost:9000/1119bb90-88ba-4894-b7f1-de26e129d977 npm run dev
```

Con la cuenta de alcance global: abrir "Siglas y equivalencias", ver TFG y MGTI, agregar "PLN" ↔ "procesamiento de lenguaje natural", intentar un duplicado (se rechaza con mensaje), editar, borrar con confirmación, y comprobar que la consulta siguiente (máximo un minuto después) usa el cambio. Con una cuenta de alcance de programa: ver la tabla sin botones de escritura, y comprobar que `POST /equivalences` por fuera responde 403.

## 6. Migración y vuelta atrás

```bash
python scripts/probar_migracion.py --url '<cadena de una copia de la base de producción>' --produccion .env.produccion --es-una-copia
DATABASE_URL=<copia> alembic downgrade 0004     # devuelve la base para poder volver a prototipo-v2-estable
```

Comprobar que `upgrade` aplica la `0005` sin tocar filas existentes, que `downgrade 0004` borra solo `sigla_equivalences`, que la versión etiquetada `prototipo-v2-estable` arranca sobre la base devuelta y que el índice de texto de Qdrant no le afecta. Guardar antes la lista con `GET /equivalences`.

## 7. Cierre

Con la opción apagada: la línea base se repite sin diferencias (SC-005). Con la opción encendida y el índice quitado (`scripts/palabras.py quitar`): las consultas responden por significado con la nota de caída (SC-009). Los resultados van a `docs/LINEA_BASE_BUSQUEDA.md` y a la tabla de resultados de [spec.md](spec.md), con la recomendación de SC-011.

## Verificado

- **Panel de siglas (T047, 2026-10-19)**: con el Microsoft simulado (`scripts/idp_simulado.py`) y el panel en desarrollo, manejado con un Chromium automatizado (Playwright, ignorando el certificado autofirmado): la cuenta global (`operador@itcr.ac.cr`) ve las semillas (MGTI con las dos redacciones y TFG), agrega "PLN" = "Procesamiento de Lenguaje Natural", el duplicado `t.f.g` = `TRABAJO final de graduación` se rechaza con «Ya existe la equivalencia «TFG» = «Trabajo Final de Graduación».», una sigla de 2 letras se rechaza antes de enviar ("La sigla debe tener de 3 a 20 caracteres."), editar y borrar (con diálogo de confirmación que explica el efecto) funcionan, y la página no registró errores de JavaScript. Con `coord.comp@itcr.ac.cr` (alcance de programa) la tabla se ve sin botones de agregar, editar ni borrar y con el aviso "Solo el alcance global puede agregar, editar o borrar equivalencias"; la escritura por fuera responde 403 `global_only` (prueba automática `tests/unit/test_equivalences.py`).
