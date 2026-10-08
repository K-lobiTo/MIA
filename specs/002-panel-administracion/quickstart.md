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

## Resultados de la validación (2026-10-08)

Corrida en local, sin tocar producción. Lo que no se pudo validar sin desplegar queda marcado como pendiente y está en el checklist de [OPERACION.md](../../docs/OPERACION.md).

| Paso | Resultado |
|---|---|
| 1. Pruebas automáticas | **Cumplido.** 208 pruebas de la API, ruff limpio, y en `web/admin/` `tsc`, 45 pruebas y `vite build`; `web/` también compila. |
| 2. Migraciones sobre una base existente | **Cumplido con una base real.** Una copia de la `mia.db` de desarrollo (esquema anterior, sin `alembic_version`, con un dominio y un documento) arrancó la API: quedó en la revisión `0002`, conservó el dominio y el documento (que aparece en "sin unidad"), y la `mia.db` original no cambió. **Pendiente: probarla contra una copia de Neon (Postgres).** Solo se ejecutó en SQLite. |
| 3. Reorganización | **Cumplido en local.** Ensayo con 26 documentos reales: simular no escribe, aplicar hace 53 cambios, la segunda corrida 0, los 911 fragmentos quedan con el dominio de su documento. Sobre la copia migrada, `--simular` da Computación con 7 dominios y Administración de Empresas con 4. **Pendiente: correrla sobre los 162 documentos de producción.** |
| 4. Panel: inventario (US1 y US2) | **Cumplido en navegador real** (Chromium): clave inválida que se vuelve a pedir, nombre repetido sin perder lo escrito, `.png` rechazado antes de subir, `.txt` que llega a "Listo" sin recargar, archivo repetido que avisa, carpeta con documentos que no se borra, búsqueda. No se probó el modo solo lectura con `INGESTION_ENABLED=false` en el navegador (sí en la API). |
| 5. Artefactos, permisos y topes (US3 y US4) | **Cumplido en navegador real** verificando cada efecto con la API: permisos por dominio y modo (403), regenerar (la anterior da 401), desactivar y reactivar, 429 con `Retry-After`, subir el tope desde el panel, otro artefacto sin afectar, aviso de la suma de topes. Se probaron con la colección vacía, así que un 200 significa "pasó el control de topes" (responde "sin información" sin llamar al modelo). **Pendiente: una consulta real con respuesta de un modelo.** |
| 6. Uso (US5) | **Cumplido en navegador real** con diez días de consultas sembradas: indicadores, filtros y registro coinciden con lo que calcula la API; gráfica con las marcas de la especificación (barra más ancha: 24 px), vista de tabla, pliegue a "Otros" con 10 modelos; CSV sin preguntas por defecto y con fórmulas neutralizadas; modo oscuro. **Pendiente: el saldo con un valor real**: se probó con una clave falsa (error HTTP real, mostrado sin romper el módulo) y con respuestas simuladas. |
| 7. Aceptación con datos reales (19 de 19) | **Pendiente.** Exige la API desplegada con los datos reorganizados y un modelo real. Está en el checklist de puesta en producción. |

### Rendimiento medido

Sobre SQLite local, con datos del tamaño real (2 unidades, 11 dominios, 60 carpetas y 162 documentos) y con diez veces más. **No incluye la latencia de red de Neon**: con Postgres remoto cada consulta SQL suma una ida y vuelta.

| Medida | Meta | 162 documentos y 3 000 consultas registradas | 1 620 documentos y 30 000 consultas |
|---|---|---|---|
| `GET /inventory` | menos de 3 s (SC-008) | 6 ms (4 consultas SQL, 29 KB) | 35 ms |
| Control de permisos y topes de una consulta | menos de 50 ms | 1 ms de cálculo, 5 consultas SQL, con índices (verificado con `EXPLAIN`) | 2 ms |
| `GET /usage?period=30d` | sin meta | 43 ms | 403 ms |
| `GET /usage/queries` (50 filas) | sin meta | 7 ms | 9 ms |

El control de permisos y topes se queda en 1 a 2 ms de cálculo; su costo real en producción es el de 5 idas y vueltas a Neon, que no se midió. Frente a los segundos que tarda el modelo en responder es despreciable. Al medir se optimizó el módulo Uso: el registro se pagina en SQL (de 571 a 9 ms con 30 000 consultas) y los indicadores usan filas simples en vez de objetos del ORM (de 822 a 403 ms); con el volumen esperado (unas 10 000 consultas al mes) `/usage` ronda los 130 ms.
