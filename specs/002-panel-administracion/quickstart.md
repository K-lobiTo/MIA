# Quickstart: validar el Panel de administración

Guía para comprobar de punta a punta que la feature funciona. Contratos en [contracts/](contracts/),
modelo en [data-model.md](data-model.md).

## Requisitos

- Entorno de la API instalado (`pip install -e ".[dev]"`), Qdrant local (`docker compose up -d qdrant`).
- Node 20 o superior para el panel.
- Las carpetas de origen en `tmp/` (para la reorganización).
- En `.env`: `ADMIN_KEY=<una clave larga>`, `DAILY_CAP_USD=3`, `CORS_ORIGINS=` (vacío en local, el panel
  usa el proxy de Vite), y los modelos por modo (`LLM_PROVIDER_LITERAL`, `LLM_MODEL_LITERAL`, etc.).

## 1. Pruebas automáticas

```bash
pytest                       # incluye las rutas nuevas, permisos, topes, reorganización y migraciones
ruff check src tests scripts
cd web/admin && npm install && npm run typecheck && npm test && npm run build
```

Esperado: todo en verde.

## 2. Migraciones sobre una base existente

```bash
cp mia.db /tmp/mia-antes.db                 # una base SQLite creada con la versión actual
DATABASE_URL=sqlite:////tmp/mia-antes.db uvicorn mia.api.main:app --port 8001
```

Esperado: la API arranca, la base queda marcada en `0001` y migrada a la última revisión
(`alembic_version`), y los dominios y documentos siguen ahí (dominios sin unidad aparecen en
`unassigned_domains` de `GET /inventory`).

## 3. Reorganización (primero en local, después en producción)

```bash
python scripts/reorganizar_v2.py --simular      # muestra qué cambiaría, sin aplicar nada
python scripts/reorganizar_v2.py                # aplica
python scripts/reorganizar_v2.py                # segunda vez: "sin cambios"
```

Esperado (US1): el resumen coincide con la tabla de la sección 2.3 de
[Definicion_Requerimientos_V2.md](../../docs/Definicion_Requerimientos_V2.md) (Computación con 7
dominios, Administración de Empresas con 4), los 162 documentos siguen en `done`, y la segunda corrida
no cambia nada. En producción se corre en local con `--env-file .env.produccion`, como la ingesta (ver
[OPERACION.md](../../docs/OPERACION.md)).

## 4. Panel: inventario (US1 y US2)

```bash
uvicorn mia.api.main:app --reload
cd web/admin && npm run dev                     # MIA_API_URL=http://localhost:8000 por defecto en dev
```

1. Sin clave: se ve el árbol completo; los botones de crear y subir piden la clave; Artefactos y Uso
   no están disponibles.
2. Ingresar `ADMIN_KEY`. Crear el dominio "Pruebas" en Computación: el aviso lista qué artefactos lo
   ven.
3. Crear la carpeta "Lote 1" en "Pruebas", arrastrar dos PDF y un `.png`: el `.png` se rechaza antes de
   subir; los PDF pasan a "listo" sin recargar.
4. Volver a subir uno de los PDF: aviso "ya existía".
5. Buscar "acta": el árbol se filtra.
6. Con `INGESTION_ENABLED=false`: botones de agregar deshabilitados con explicación.

## 5. Artefactos, permisos y topes (US3 y US4)

1. Registrar "Prueba" con solo el dominio "Pruebas", solo modo literal y tope 0.05 USD. Copiar la clave
   (se muestra una vez).
2. Con esa clave:
   ```bash
   K=mia_...
   curl -s -H "X-Artifact-Key: $K" localhost:8000/domains          # solo "Pruebas"
   curl -s -H "X-Artifact-Key: $K" localhost:8000/config           # solo modo literal
   curl -s -X POST -H "X-Artifact-Key: $K" -H "content-type: application/json" \
     -d '{"domains":["<id de otro dominio>"],"question":"hola"}' localhost:8000/query   # 403
   curl -s -X POST -H "X-Artifact-Key: $K" -H "content-type: application/json" \
     -d '{"domains":["<id de Pruebas>"],"question":"...","mode":"razonamiento"}' localhost:8000/query  # 403
   ```
3. Hacer consultas literales hasta pasar 0.05 USD: la siguiente responde 429 con `Retry-After`; otro
   artefacto sigue respondiendo. Subir el tope en el panel: la consulta siguiente funciona.
4. Regenerar la clave: la anterior da 401. Desactivar: 403. Reactivar: vuelve a funcionar.
5. Registrar las dos instancias de la Consulta administrativa (unidad completa, ambos modos) y
   verificar con la clave de Administración de Empresas que un dominio de Computación da 403.

## 6. Uso (US5)

1. Abrir Uso con período "hoy": indicadores, gráfica por hora y tablas reflejan las consultas de los
   pasos anteriores, incluidas las rechazadas (con su motivo, costo 0).
2. Cambiar el desglose a modo y a modelo, y el período a 7 días (gráfica por día).
3. Abrir una consulta: pregunta, dominios, fuentes y calificación.
4. Descargar CSV: sin la columna de preguntas salvo que se marque incluirlas.
5. Comparar el gasto del día con el panel *Activity* de OpenRouter: diferencia menor al 5 % (SC-007).

## 7. Aceptación con datos reales

```bash
python scripts/pruebas_mvp.py --url http://localhost:8000 --clave mia_...   # 19 de 19 en modo literal
```
