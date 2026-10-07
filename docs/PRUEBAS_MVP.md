# Pruebas de aceptación del MVP

Estado de los criterios de aceptación de la sección 11 de [Definicion_Requerimientos_MVP.md](Definicion_Requerimientos_MVP.md), con el conjunto de datos y las preguntas usadas para verificarlos. Las preguntas se corren con `scripts/pruebas_mvp.py`, así que cualquiera puede repetir la verificación.

## Datos cargados (desde 2026-10-06)

Documentos reales entregados por Mauricio Arroyo (Unidad de Posgrado en Computación) y Martín Solís (Maestría en Analítica de Negocios). Reemplazaron a los datos de prueba del MVP (ver "Historial" al final). Los archivos no se versionan (`tmp/` está en `.gitignore`).

| Dominio | Carpeta de origen (`tmp/`) | Documentos | Fragmentos |
|---|---|---|---|
| Analítica de Negocios: Consejo de Área | `Información_analítica_de_negocios/ACTAS` | 6 actas de 2026 (DOCX) | 56 |
| Analítica de Negocios: Currículum | `Información_analítica_de_negocios/` `PROGRAMAS CURSO`, `DOCUMENTOS GENERALES PROGRAMA`, `LINEAS TFG`, `REGLAMENTOS DEL PROGRAMA` | 23: 17 programas de curso, documento del programa, enlace a la página web, líneas de TFG, 3 reglamentos | 505 |
| Computación: Planes de estudio | `Información_unidad_postgrados_computación/Planes de estudio` (MCC, MCSg, MGTI) | 83: planes, programas de curso, reformas y acuerdos curriculares | 1723 |
| Computación: Proyectos de graduación | `Información_unidad_postgrados_computación/Proyectos Finales de Graduación` | 30 tesis, informes y artículos (PDF) | 3526 |

Total: 142 documentos y 5810 fragmentos.

**Lo que no se cargó:**
- **Actas del Consejo de la Unidad de Posgrado en Computación** (`Memorias del consejo/2025`, 20 actas): contienen datos personales de estudiantes. Ver "Datos y privacidad" en [OPERACION.md](OPERACION.md).
- **Afiches de apertura y promoción** (`Aperturas_promoción`, 39 imágenes JPG y PNG): MIA solo lee PDF, DOCX y TXT. Requieren reconocimiento de texto (OCR) o un modelo con visión.
- **`Planes de estudio/MCC/Electivas.pdf`**: es un escaneo sin capa de texto (mismo motivo).
- **`Docentes`**: la carpeta llegó vacía.

**Cómo se cargaron**, con la API local contra producción (ver "Cargar documentos" en [OPERACION.md](OPERACION.md)):

```bash
U=http://localhost:8010
C="tmp/Información_unidad_postgrados_computación"; A="tmp/Información_analítica_de_negocios"
python scripts/cargar_carpeta.py --url $U --dominio "Analítica de Negocios: Consejo de Área" \
  --descripcion "Actas de las sesiones 2026 del Consejo de Área Académica de la Maestría en Analítica de Negocios" "$A/ACTAS"
python scripts/cargar_carpeta.py --url $U --dominio "Analítica de Negocios: Currículum" \
  --descripcion "Programas de curso, documento del programa, líneas de TFG y reglamentos de la Maestría en Analítica de Negocios" \
  "$A/PROGRAMAS CURSO" "$A/DOCUMENTOS GENERALES PROGRAMA" "$A/LINEAS TFG" "$A/REGLAMENTOS DEL PROGRAMA"
python scripts/cargar_carpeta.py --url $U --dominio "Computación: Planes de estudio" \
  --descripcion "Planes de estudio, programas de curso, reformas y acuerdos curriculares de las maestrías en Ciencia de la Computación, Ciberseguridad y Gerencia de Tecnologías de la Información" \
  --excluir "Electivas.pdf" "$C/Planes de estudio"
python scripts/cargar_carpeta.py --url $U --dominio "Computación: Proyectos de graduación" \
  --descripcion "Tesis, informes y artículos finales de graduación de estudiantes de la Unidad de Posgrado en Computación" \
  "$C/Proyectos Finales de Graduación"
```

## Cómo correr las pruebas

```bash
python scripts/pruebas_mvp.py --url https://mia-api-5qgh.onrender.com   # producción
python scripts/pruebas_mvp.py --url http://localhost:8000               # local
python scripts/pruebas_mvp.py --url <url> --solo U4,I1                  # algunos casos
```

El script solo usa la biblioteca estándar de Python. Busca los dominios por nombre y, para cada caso, verifica una de dos cosas:
- que la API responda con contenido y cite el documento esperado (y, en algunos casos, que la respuesta contenga un dato concreto, p. ej. "14" horas o el último punto de una lista, para detectar respuestas incorrectas o cortadas);
- o que responda "sin información" sin listar fuentes.

Reintenta hasta 3 veces ante un 502 (Gemini gratuito se satura seguido). Termina con código 1 si algún caso falla.

## Casos

| Id | Dominios | Pregunta | Esperado |
|---|---|---|---|
| A1 | AN Consejo | ¿Qué se discutió sobre becas en caso de superar los 25 estudiantes admitidos? | Respuesta, cita acta 04-2026 |
| A2 | AN Consejo | ¿Quién fue designado coordinador específico del proyecto ante FUNDATEC? | Respuesta, cita acta 01-2026, menciona a Martín Solís |
| A3 | AN Consejo | ¿Qué se discutió sobre becas y descuentos para funcionarios del TEC? | Respuesta, cita acta 03-2026 |
| U1 | AN Currículum | ¿Cuántas horas extraclase por semana tiene el curso Big Data para Negocios? | Respuesta "14", cita su programa |
| U2 | AN Currículum | ¿De qué curso es requisito Big Data para Negocios? | Respuesta, cita su programa |
| U3 | AN Currículum | ¿Cada cuánto se abre el proceso de admisión al programa? | Respuesta "cada año", cita el Reglamento del Programa |
| U4 | AN Currículum | ¿Cuáles son las líneas de TFG de la maestría? | Las seis líneas, hasta "Analítica de Texto"; cita Líneas de TFG |
| P1 | CO Planes | ¿Cuántas horas extraclase por semana tiene el curso Cibercrimen? | Respuesta "14", cita MC3010 |
| P2 | CO Planes | ¿Cuántos créditos tiene el curso Cibercrimen y en qué área del plan de estudios se ubica? | Respuesta "4", cita MC3010 |
| G1 | CO Proyectos | ¿Qué trabajo de graduación trata sobre drones en aeropuertos? | Respuesta, cita el trabajo de César Jiménez |
| G2 | CO Proyectos | ¿Qué compara el análisis de modelos centralizados y descentralizados en sistemas de pagos? | Respuesta, cita el trabajo de Luis Alvarado |
| N1 | Los cuatro | ¿Cuál es la receta del gallo pinto? | Sin información |
| X1 | AN Currículum + CO Planes | La pregunta de P1 | Respuesta "14", cita MC3010 |
| I1 | AN Currículum | La pregunta de P1, en el dominio equivocado | Sin información |
| I2 | CO Proyectos | La pregunta de A1, en el dominio equivocado | Sin información |

Grupos: A (actas), U y P (currículum de cada programa), G (proyectos de graduación), N (sin respuesta en ningún dominio), X (multi-dominio), I (aislamiento entre dominios).

U1, U2, P1 y P2 dependen de que el lector de DOCX lea tablas: en los programas de curso, créditos, horas y requisitos están en tablas (ver [ARQUITECTURA.md](ARQUITECTURA.md)). U4 depende de que los documentos cortos se pasen completos al LLM.

## Resultado (2026-10-06, API local con los datos de producción + Gemini)

**15 de 15 casos correctos.** Observaciones:
- **U4 (líneas de TFG):** con solo los fragmentos relevantes y sus vecinos, la respuesta listaba 3 de las 6 líneas sin avisar que faltaban. La lista ocupa casi todo el documento (9 fragmentos). Se resolvió pasando completos al LLM los documentos de hasta 12 fragmentos (`QUERY_FULL_DOCUMENT_MAX_CHUNKS`, ver `src/mia/rag/context.py`).
- **Siglas:** "¿Qué líneas de trabajo final de graduación ofrece la maestría?" responde "sin información", mientras que con "TFG" responde bien: la forma desarrollada no alcanza el umbral de similitud contra un documento que usa la sigla. Limitación conocida de la búsqueda; candidata a resolverse en la versión 3 (expansión de la pregunta o búsqueda híbrida por palabras clave).
- **Fuentes:** como en el MVP, la lista de fuentes incluye documentos que se pasaron al LLM aunque no aportaron a la respuesta (p. ej. U1 lista seis documentos).

## Estado de los criterios de aceptación

| # | Criterio | Estado | Evidencia |
|---|---|---|---|
| 1 | Se crea el dominio de memoria del Consejo | Cumplido | "Analítica de Negocios: Consejo de Área" (las actas de Computación no se cargaron por privacidad). |
| 2 | Se suben al menos 3 a 5 actas reales (PDF o DOCX) | Cumplido | 6 actas reales en DOCX del Consejo de Área de Analítica de Negocios. |
| 3 | Preguntas representativas: las que tienen respuesta citan el documento y dominio de origen; las que no, responden "sin información" sin fuentes | Cumplido | 15 de 15 casos: 12 con respuesta citan el documento correcto; 3 sin respuesta no inventan ni listan fuentes (N1, I1, I2). |
| 4 | Subir el mismo archivo dos veces no duplica fragmentos | Cumplido | Verificado el 2026-09-28 con los datos de prueba; `cargar_carpeta.py` se apoya en el mismo mecanismo. |
| 5 | Todo el stack levanta con `docker compose up` sin pasos manuales adicionales | Cumplido | Verificado el 2026-09-27 con un `.env` copiado de `.env.example`. |

## Historial: datos de prueba del MVP (hasta 2026-10-05)

El MVP se validó con 3 actas públicas del Consejo Institucional del TEC (sesiones 3436 a 3438, de 96 a 180 páginas) en el dominio "Memoria del Consejo", y 4 programas de curso de la Maestría en Computación en "Currículum": 1245 fragmentos en total. El 2026-09-28 dio 18 de 18 casos correctos contra Render, después de sumar los fragmentos vecinos al contexto (antes, las respuestas sobre listas largas quedaban incompletas). Esos datos se borraron de producción el 2026-10-06 al cargar los documentos reales; los archivos siguen en `tmp/dominios/`. Las preguntas de esa versión están en el historial de git de `scripts/pruebas_mvp.py`.
