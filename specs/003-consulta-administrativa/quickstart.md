# Quickstart: validar la Consulta administrativa

Guía para comprobar de punta a punta que la entrega cumple el spec. Contratos en
[contracts/](contracts/), estado de la Consulta en [data-model.md](data-model.md).

## Requisitos

- Rama `dev`, entorno de Python activo (`source .venv/bin/activate`) y Node 20 o superior.
- Una API con datos: local (`uvicorn mia.api.main:app --reload` con Qdrant local) o producción en
  Railway.
- Desde el panel (`web/admin/`), con la clave de administración, tres artefactos:
  - **Prueba Computación**: unidad Computación completa, ambos modos.
  - **Prueba Administración**: unidad Administración de Empresas completa, ambos modos.
  - **Prueba restringida**: un solo dominio, solo modo literal.

## 1. Pruebas automáticas

```bash
pytest
ruff check src tests scripts
cd web/consulta && npm install && npm run typecheck && npm test && npm run build
cd ../admin && npm run build   # el panel sigue compilando
```

Esperado: todo en verde. Las pruebas nuevas cubren la instrucción y la cantidad de fragmentos por
modo, `no_info`, el largo de la pregunta, el formateador, la agrupación y el recuerdo de dominios, y
la resolución de modos disponibles.

## 2. Abrir la Consulta

```bash
cd web/consulta
MIA_API_URL=http://localhost:8000 npm run dev          # o la URL de Railway
```

En `http://localhost:3000`:

1. Pide la clave. Con la de **Prueba Computación**: el encabezado y la pestaña dicen su nombre, se
   ven solo los dominios de Computación y el selector de modo con sus dos opciones explicadas.
2. Recargar: no pide la clave otra vez, conserva dominios y modo, y la conversación está vacía.
3. "Ninguno": no deja enviar y dice "Elige al menos un dominio."

## 3. Modo literal (Historia 1)

Pregunta sobre un acuerdo de un acta, en Memoria del Consejo:

- Respuesta con formato, fuentes con su dominio y fragmentos desplegables; pie "Literal · N s".
- Una pregunta sin respuesta en los documentos ("¿Cuál es el horario de la cafetería?"): aspecto
  distinto, sin fuentes.

## 4. Modo con razonamiento (Historia 2, criterio 7)

En Currículum, modo "Con razonamiento":

> ¿Cuántos créditos suman Sistemas Operativos Avanzados, Análisis de Algoritmos y Diseño de
> Experimentos?

Esperado: mientras espera, el aviso de que puede tardar más; la respuesta tiene **Lo que dicen los
documentos** (los créditos de cada curso con su programa) y **Conclusión** con
`4 + 4 + 4 = 12`; cita los tres programas; pie "Con razonamiento · N s".

## 5. Aislamiento entre instancias (criterio 17)

```bash
# Con la clave de Prueba Administración, un dominio de Computación: debe dar 403
curl -s -X POST <api>/query -H "X-Artifact-Key: <clave administración>" \
  -H "content-type: application/json" -d '{"domains": ["<id dominio de Computación>"], "question": "x"}'
```

Repetir al revés. Con la clave de **Prueba restringida**, la Consulta muestra un solo dominio y no
muestra el selector de modo.

## 6. Topes y modos no disponibles (Historia 3, criterios 8 y 9)

1. En el panel, tope de razonamiento de **Prueba Computación** en 0.01 USD. Hacer preguntas con
   razonamiento hasta alcanzarlo: la opción queda deshabilitada con el motivo, el literal sigue
   funcionando y en la Consulta de **Prueba Administración** el razonamiento sigue disponible.
2. Subir el tope en el panel: la pregunta siguiente funciona sin recargar nada en la API.
3. En una API local sin `LLM_PROVIDER_RAZONAMIENTO`: la opción aparece deshabilitada con
   "La instancia no tiene configurado un modelo para este modo."
4. Desactivar el artefacto en el panel y preguntar: mensaje de desactivado, sin reintentar.
5. Regenerar la clave en el panel y preguntar: la Consulta pide la clave nueva.

## 7. Errores y reintentos (CON-7)

Con la API local detenida, preguntar: "No se pudo conectar con MIA" y "Reintentar". En razonamiento
con un modelo inexistente configurado (502): aparece además "Reintentar en modo literal", que
responde.

## 8. Calificación (Historia 4, criterio 10)

Marcar una respuesta "No útil" con un comentario. En el panel, módulo Uso, registro de consultas: la
consulta aparece con esa calificación y ese comentario. Cambiar a "Útil": el registro muestra la
nueva.

## 9. Dominio nuevo sin reiniciar (Historia 5, criterio 1)

Crear desde el panel un dominio en la unidad Computación. Recargar la Consulta de **Prueba
Computación**: aparece. En la de **Prueba Administración**: no.

## 10. Aceptación y publicación

```bash
python scripts/pruebas_mvp.py --url <api> --clave mia_...                    # 19 de 19
python scripts/pruebas_mvp.py --url <api> --clave mia_... --modo razonamiento # informativo
```

Publicación (la hace quien administra MIA, ver `docs/OPERACION.md`): dos sitios estáticos desde
`web/consulta`, direcciones en `CORS_ORIGINS`; cada dirección recuerda su propia clave.

## 11. Rendimiento (SC-008)

En el módulo Uso, filtrar por los artefactos de prueba y descargar el CSV del registro: el 90 % de las
consultas literales por debajo de 15 s y el 90 % de las de razonamiento por debajo de 90 s. Los
indicadores del módulo (mediana y 95 %) sirven de referencia rápida: si el 95 % ya está por debajo de
la meta, el 90 % también.

## Resultados de la validación (2026-10-08)

Corrida en local: la API nueva (rama `dev`) en el puerto 8010 con los datos reales de producción (Neon y Qdrant Cloud, vía `.env.produccion`, con la configuración de modelos de Railway) y la Consulta en el puerto 3000 con el proxy de Vite. Cuatro artefactos de prueba (`PRUEBA ...`), ya desactivados. Costo total de las pruebas: unos 0.09 USD.

| Paso | Resultado |
|---|---|
| 1. Pruebas automáticas | **Cumplido.** 234 pruebas de la API, `ruff` limpio; en `web/consulta/` `tsc`, 54 pruebas y `vite build`; `web/admin/` sigue compilando. |
| 2. Abrir la Consulta | **Cumplido en navegador real** (Chromium): pide la clave, muestra el nombre real de la instancia, los 7 dominios de Computación y el selector de modo; al recargar conserva clave, dominios y modo, y la conversación queda vacía; sin dominios no deja enviar. |
| 3. Modo literal | **Cumplido** con datos reales: una pregunta sobre Deep Learning por tutoría cita actas, pie "Literal · 3,8 s". La pregunta sin respuesta se probó con la API simulada (estilo propio, sin fuentes) y en `pruebas_mvp.py` (N1). |
| 4. Modo con razonamiento (criterio 7) | **Cumplido en lo esencial.** Responde **12**, con las dos partes ("Lo que dicen los documentos" y "Cálculo o conclusión", con `4 + 4 + 4 = 12`) y cita el documento de cada dato. **Límite:** las fuentes devueltas son el Catálogo, la Reforma curricular, el programa de MC6004 o el de MC6102 según la corrida; el programa de MC6104 (Diseño de Experimentos) no apareció en las fuentes, porque el dato lo trajeron el Catálogo y la Reforma. Es el límite conocido de la recuperación (sección 3.3), no de la instrucción. |
| 5. Aislamiento (criterio 17) | **Cumplido.** Administración de Empresas ve 4 dominios y ninguno de Computación; consultar uno de Computación con la clave de Administración da 403, y al revés. La instancia restringida muestra un dominio y no muestra el selector de modo. |
| 6. Topes y modos (criterio 8) | **Cumplido.** Con el tope de razonamiento bajo, la opción queda deshabilitada con su motivo, el literal sigue y otro artefacto conserva el razonamiento; al subir el tope vuelve a estar disponible. Desactivar da el mensaje de "desactivado" sin reintentar; regenerar la clave hace que la Consulta pida la nueva. El caso del modo no configurado (criterio 9) se cubrió con pruebas automáticas y con la API simulada. |
| 7. Errores y reintentos | **Cumplido con la API simulada** (502, 429, sin conexión): "Reintentar" y "Reintentar en modo literal" en razonamiento. |
| 8. Calificación (criterio 10) | **Cumplido.** La calificación "No útil" con su comentario aparece en el registro de consultas (`GET /usage/queries`). |
| 9. Dominio nuevo sin reiniciar (criterio 1) | **No se probó en producción**: no hay forma de borrar un dominio y no se quiso dejar uno de prueba en el inventario real. Lo cubren las pruebas automáticas de permisos (un dominio creado después de configurar el acceso por unidad queda visible). |
| 10. Aceptación y publicación | **19 de 19 en modo literal** y, informativo, **19 de 19 en modo con razonamiento**. La publicación de los dos sitios en Render queda para quien administra MIA. |
| 11. Rendimiento (SC-008) | **Cumplido.** Literal (21 consultas): mediana 3,1 s, 90 % por debajo de 5,8 s, máximo 13,2 s. Razonamiento (21 consultas): mediana 5,3 s, 90 % por debajo de 7,4 s, máximo 8,7 s. Metas: 15 s y 90 s. |
| SC-001 (primera pregunta en menos de 2 minutos) | **Pendiente.** Exige a una persona que no conozca la Consulta; se medirá en la evaluación con usuarios. |

Las pruebas en navegador cubrieron además pantalla de celular (375 px, sin desplazamiento horizontal), modo claro y oscuro, y que el HTML que devuelva el modelo se muestra como texto.

### Ajuste de la instrucción con razonamiento (2026-10-08)

Tras probar la Consulta con usuarios reales se renombró la segunda parte de la respuesta con razonamiento a **Conclusión** (antes "Cálculo o conclusión") y se amplió la instrucción a comparar, contrastar y resumir, para que no fuerce una operación cuando la pregunta no es numérica. Validado contra los datos reales: la pregunta de créditos sigue respondiendo **12** (`4 + 4 + 4 = 12` dentro de la conclusión), una síntesis sobre becas en las actas no inventa ninguna operación, y una comparación de horas concluye que son iguales con los datos de cada curso. También se acortó la vista de los fragmentos citados (260 caracteres con "Ver más").
