# Pruebas de aceptación del MVP

Estado de los criterios de aceptación de la sección 11 de [Definicion_Requerimientos_MVP.md](Definicion_Requerimientos_MVP.md), con el conjunto de datos y las preguntas usadas para verificarlos. Las preguntas se corren con `scripts/pruebas_mvp.py`, así que cualquiera puede repetir la verificación.

## Datos de prueba

Los archivos no se versionan (`tmp/` está en `.gitignore`). Estructura esperada:

```
tmp/dominios/
├── Memoria_Del_Consejo/Actas/          dominio "Memoria del Consejo"
│   ├── acta-aprobada-3436.pdf          Consejo Institucional del TEC, 21 ene 2026, 96 págs.
│   ├── acta-aprobada-3437.pdf          28 ene 2026, 180 págs.
│   └── acta-aprobada-3438.pdf          04 feb 2026, 113 págs.
└── Currículum/Programas_de_Curso/      dominio "Currículum"
    ├── MC6004-Sistemas Operativos Avanzados.pdf
    ├── MC6102-Análisis de Algoritmos.pdf
    ├── MC6104-Diseño de Experimentos.pdf
    └── MC7201-Introducción a la Investigación.pdf
```

Las actas son públicas y se descargan del sitio del Consejo Institucional del TEC. Los programas de curso son de la Maestría en Computación (vigentes desde el I Semestre 2020). En total: 1245 fragmentos en Qdrant (1189 de actas y 56 de programas).

Para cargarlos en una instancia nueva: crear los dominios con esos nombres exactos y subir los archivos, siguiendo "Cargar actas (ingesta)" en [OPERACION.md](OPERACION.md).

## Cómo correr las pruebas

```bash
python scripts/pruebas_mvp.py --url https://mia-api-5qgh.onrender.com   # producción
python scripts/pruebas_mvp.py --url http://localhost:8000               # local
python scripts/pruebas_mvp.py --url <url> --solo C1,CU6                 # algunos casos
```

El script solo usa la biblioteca estándar de Python. Busca los dominios por nombre y, para cada caso, verifica una de dos cosas:
- que la API responda con contenido y cite el documento esperado;
- o que responda "sin información" sin listar fuentes.

Reintenta hasta 3 veces ante un 502 (Gemini gratuito se satura seguido). Termina con código 1 si algún caso falla.

## Casos

| Id | Dominios | Pregunta | Esperado |
|---|---|---|---|
| M1 | Memoria | ¿Cuánto se pagará de dietas a los estudiantes? | Respuesta, cita 3437 |
| M2 | Memoria | ¿Se aprobó el acta 3435? | Respuesta, cita 3438 |
| M3 | Memoria | ¿Cómo está conformado el Consejo Institucional? | Respuesta, cita 3437 |
| M4 | Memoria | ¿Qué se aprobó sobre el Plan Táctico Institucional 2026-2028? | Respuesta, cita 3438 |
| M5 | Memoria | ¿Qué se acordó sobre el programa de inglés? | Respuesta, cita 3438 |
| M6 | Memoria | ¿Cuándo abre la matrícula de la maestría en Computación? | Sin información |
| M7 | Memoria | ¿Cuál es la receta del gallo pinto? | Sin información |
| C1 | Currículum | ¿Cómo se evalúa el curso Análisis y Diseño de Algoritmos? | Respuesta, cita MC6102 |
| C2 | Currículum | ¿Qué requisitos tiene el curso Diseño de Experimentos? | Respuesta, cita MC6104 |
| C3 | Currículum | ¿De qué curso es requisito Sistemas Operativos Avanzados? | Respuesta, cita MC6004 |
| C4 | Currículum | ¿Cuántos créditos tiene el curso Introducción a la Investigación? | Respuesta, cita MC7201 |
| CU1 | Memoria | Caso de uso 1: acuerdos del Consejo de Unidad sobre la maestría de Ciberseguridad | Sin información (ver nota) |
| CU6 | Currículum + Memoria | Caso de uso 6: cambios al programa de la maestría en Ciencia de la Computación | Sin información (ver nota) |
| X1 | Currículum + Memoria | ¿Cómo se evalúa el curso Análisis y Diseño de Algoritmos? | Respuesta, cita MC6102 |
| X2 | Currículum + Memoria | ¿Desde cuándo está vigente el programa del curso Diseño de Experimentos? | Respuesta, cita MC6104 |
| A1 | Memoria | La pregunta de C1, en el dominio equivocado | Sin información |
| A2 | Currículum | La pregunta de M5, en el dominio equivocado | Sin información |

Grupos: M (actas), C (programas de curso), CU (casos de uso del documento conceptual), X (consultas multi-dominio), A (aislamiento entre dominios: una pregunta no se responde con el dominio equivocado).

**Nota sobre CU1 y CU6:** con estos datos, lo correcto es "sin información".
- CU1: las actas cargadas son del Consejo Institucional, no del Consejo de Unidad, y no mencionan Ciberseguridad.
- CU6: los programas de curso describen el estado vigente sin historial de cambios, algo que el documento conceptual ya advertía ("el caso 6 depende de que Currículum también capture el historial de cambios").

Por esta falta de documentos, el criterio 3 de aceptación se generalizó el 2026-09-28 para no depender de estos dos casos de uso (ver sección 11 de [Definicion_Requerimientos_MVP.md](Definicion_Requerimientos_MVP.md)). Si más adelante se cargan actas del Consejo de Unidad o versiones anteriores de los programas, cambiar la expectativa de CU1 y CU6 a "respuesta" en el script.

## Resultado (2026-09-28, producción: Render + Neon + Qdrant Cloud + Gemini)

**17 de 17 casos correctos.** Observaciones:
- **M5 (programa de inglés):** la respuesta es parcial. El fragmento con la parte resolutiva del acuerdo no quedó entre los 5 recuperados, y el LLM lo aclara. Primera mejora a probar: `QUERY_SEARCH_LIMIT` en 8 o 10.
- **Gemini saturado:** en corridas anteriores, algunas consultas devolvieron 502 por saturación de Gemini y funcionaron al reintentar.

## Estado de los criterios de aceptación

| # | Criterio | Estado | Evidencia |
|---|---|---|---|
| 1 | Se crea el dominio "Memoria del Consejo" | Cumplido | Existe en producción, junto con "Currículum". |
| 2 | Se suben al menos 3 a 5 actas reales (PDF o DOCX) | Cumplido | 3 actas reales en PDF (96 a 180 páginas). |
| 3 | Preguntas representativas: las que tienen respuesta citan el documento y dominio de origen; las que no, responden "sin información" sin fuentes | Cumplido | 17 de 17 casos: 11 con respuesta citan el documento correcto (M1 a M5, C1 a C4, X1, X2); 6 sin respuesta no inventan ni listan fuentes (M6, M7, CU1, CU6, A1, A2). |
| 4 | Subir el mismo archivo dos veces no duplica fragmentos | Cumplido | En producción: resubir `MC6102` devolvió el documento existente; 1245 fragmentos antes y después. |
| 5 | Todo el stack levanta con `docker compose up` sin pasos manuales adicionales | Cumplido | Verificado el 2026-09-27 con un `.env` copiado de `.env.example`. |
