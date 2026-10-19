# Quickstart: validar la pregunta limpia

Contrato en [contracts/pregunta-limpia.md](contracts/pregunta-limpia.md) y estructuras en [data-model.md](data-model.md). Referencias de comparación: las corridas `base`, `control` y `control7` de las features 005 a 007 ([LINEA_BASE_BUSQUEDA.md](../../docs/LINEA_BASE_BUSQUEDA.md)).

## 1. Pruebas automáticas (sin red)

```bash
source .venv/bin/activate
pytest tests/unit/test_query_rewrite.py tests/unit/test_query_clean_question.py tests/unit/test_linea_base.py
pytest                    # toda la suite
ruff check src tests scripts
```

Deben pasar: la tabla de reglas (identificación, descripción, cortesías, con y sin tildes y signos, mayúsculas), las guardas (menos de 3 caracteres, igual a la pregunta, más de 8 palabras, cláusulas, más de una pregunta), los negativos, la variable y su valor inválido, la ruta con la opción apagada (sin cambios) y encendida (con segundo intento que encuentra, que no encuentra, que ya no hace falta, con modelo que responde "sin información"), la nota en Uso y que el segundo intento no agrega llamadas al modelo.

## 2. Anticipar el efecto sin gasto (solo lectura)

```bash
python scripts/linea_base.py puntajes --etiqueta limpia-previa --env-file .env.produccion
```

Muestra, para cada caso donde la reducción aplica, el puntaje y el puesto del documento esperado con la variante `limpia` frente a la completa. Con S22-1, S22-3 y S22-4 se espera lo ya medido con el nombre solo (0,833, 0,807 y 0,827 contra un umbral de 0,82). Si la variante limpia no mejora algún caso, no tiene sentido gastar en `respuestas` para ese caso.

## 3. Mediciones en producción (con autorización y tope de gasto)

Requisitos: `.env` con `MIA_ARTIFACT_KEY` y `MIA_ADMIN_KEY`, un artefacto de prueba activo con acceso a los dominios de los casos, y una autorización del usuario con el tope de gasto por corrida.

```bash
# Control: opción apagada, código de dev
railway variable set QUERY_CLEAN_QUESTION=off -s MIA --skip-deploys
python scripts/servicios.py encender MIA --forzar --ref origin/dev
python scripts/linea_base.py respuestas --etiqueta control8 --url https://mia-main.up.railway.app --tope-usd 0.40

# Opción encendida
railway variable set QUERY_CLEAN_QUESTION=on -s MIA --skip-deploys
python scripts/servicios.py encender MIA --forzar --ref origin/dev
python scripts/linea_base.py respuestas --etiqueta limpia --url https://mia-main.up.railway.app --tope-usd 0.40

# Comparar y apagar
python scripts/linea_base.py comparar control8 limpia
python scripts/linea_base.py informe limpia
python scripts/servicios.py apagar MIA --forzar
```

`railway variable set` sin `--skip-deploys` redespliega desde `main` y pierde el código de `dev`: comprobarlo siempre (los tokens y `railway deployment list -s MIA --json`).

## 4. Qué debe verse

- Casos de envoltura sobre personas cuya forma corta pasa el umbral: de "sin información" (control) a respuesta con el documento esperado (opción encendida).
- Negativos (`sin_pregunta_limpia`): sin nota de pregunta limpia en Uso.
- Los 19 casos de la batería del MVP: sin cambios de resultado atribuibles a la opción; los que de verdad no tienen información siguen respondiendo "sin información".
- El número de consultas con segundo intento y cuántas pasaron el umbral, por modo.
- Costo y latencia de las consultas sin segundo intento dentro del ruido del control.

## 5. Cierre

Dejar la variable en `off`, la API apagada, el artefacto de prueba desactivado y su clave regenerada, y documentar el resultado en `docs/LINEA_BASE_BUSQUEDA.md` y en la sección de BUS-1 de `docs/Definicion_Requerimientos_V3.md`.
