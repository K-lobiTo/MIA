# Quickstart: validar la aclaración de programa y el contexto

De lo más barato (pruebas automáticas) a lo real (producción, solo con tu autorización). Diseño en [research.md](research.md), [data-model.md](data-model.md) y [contracts/](contracts/). Todo el desarrollo se hace en `dev`.

## 0. Prerrequisitos

```bash
source .venv/bin/activate && pip install -e ".[dev]" && pip install -e "./whatsapp[dev]"
docker compose up -d qdrant           # Qdrant local (para la medición del paso 2)
```

## 1. Pruebas automáticas (sin red y sin cuota)

```bash
pytest tests/unit/test_programs.py tests/unit/test_bot_clarify.py tests/unit/test_bot_end_to_end.py
pytest whatsapp/tests/test_context.py whatsapp/tests/test_flow_clarify.py
pytest && ruff check src tests scripts whatsapp
```

Lo que deben demostrar:
- **Programa**: título a nombre natural y clave (mayúsculas, tildes, palabras de enlace, "(Business Analytics)"), documentos sin título con la forma y su caché.
- **API**: con `BOT_CLARIFY=on`, una pregunta ambigua entre dos programas devuelve `clarify` con los dos y `no_info`; con un solo programa o ninguno, "sin información" como hoy; con `off`, igual que antes; la respuesta con fuentes trae `programs`; `POST /query` responde exactamente igual (misma forma, sin `clarify` ni `programs`) y sin búsqueda extra.
- **Contexto**: nunca más de 4 turnos, vence por inactividad, respeta el tope de personas, no guarda el texto del bot y no deja datos en los registros.
- **Servicio**: pregunta ambigua da aclaración numerada; "Ciberseguridad", "la de analítica" y "2" la resuelven; "no sé", "las dos" o un programa que no es candidato la descartan y no vuelven a preguntar; la aclaración vencida no se resuelve; el programa recordado reintenta una vez y no encadena; nombrar otro programa lo cambia; una pregunta que ya se responde no cambia.
- **De punta a punta** (`test_bot_end_to_end.py`): el servicio y la API reales en un proceso, con Kapso, el almacén y el modelo simulados: aclaración, resolución con respuesta citada, y 4 mensajes de cuota contados.
- **Sin regresiones**: las pruebas existentes pasan y la batería del MVP da 19 de 19.

## 2. Calibrar la aclaración con los documentos reales (research R9)

Con los seis documentos de Ciberseguridad y Analítica en una carpeta (por ejemplo `tmp/nuevos/`) y un Qdrant local, correr `python scripts/calibrar_aclaracion.py --documentos tmp/nuevos`: ingiere los documentos en una colección temporal con el mismo modelo de embeddings, recorre los casos de `scripts/datos/casos_aclaracion.json` y para cada pregunta imprime el mejor puntaje, las palabras con contenido y los programas candidatos (sale con código 1 si algún caso no se comporta como se espera). Las preguntas que ya pasan `QUERY_SIMILARITY_THRESHOLD` las responde el modelo y no entran a la aclaración. Los tipos de caso:

| Tipo | Preguntas de ejemplo | Debe dar |
|---|---|---|
| Ambiguas entre programas | "¿Cuándo empiezan las lecciones?", "¿Cuánto cuesta?", "¿Cuáles son los requisitos?", "¿Cómo me postulo?" | Dos programas con un fragmento sobre el piso y con evidencia léxica (las que pasan el umbral de 0,82 las responde el modelo) |
| Con un solo programa | "¿Cuántos estudiantes se aceptan?" (solo Analítica lo dice) | Un programa o ninguno |
| Sin relación | "¿Cuánto cuesta la luna?", "¿Qué hora es?" | Ningún programa |

Si cambian los documentos o el modelo, repetir la medición y ajustar `BOT_CLARIFY_MIN_SIMILARITY` (piso, 0,70) y `BOT_CLARIFY_CANDIDATES` (30); los resultados de la última medición están en research R9.

## 3. Recorrer el flujo con el servicio local (sin Kapso)

Como el paso 2 de [011 quickstart](../011-bot-whatsapp-kapso/quickstart.md) (API local, `kapso_falso.py` y el bot), con `BOT_CLARIFY=on`:

1. Enviar "¿Cuándo empiezan las lecciones?": el Kapso falso imprime la aclaración con los dos programas numerados.
2. Contestar "ciberseguridad" (mismo `--persona`): llega la fecha de inicio de Ciberseguridad con su fuente.
3. Preguntar "¿y cuánto cuesta?": responde para Ciberseguridad (o dice que no tiene el dato de ese programa), sin volver a preguntar.
4. Repetir con otra `--persona` y contestar "no sé": responde "sin información" y no vuelve a preguntar.
5. Esperar el vencimiento (`BOT_CONTEXT_MINUTES=1`) y contestar "ciberseguridad": se trata como mensaje nuevo.
6. Mirar el registro del servicio: aparece `resultado=aclaracion`, sin textos, teléfonos ni nombres de programas.

## 4. Producción (solo con tu autorización)

1. Merge de `dev` a `main` y `git push origin main`.
2. Desplegar `MIA` y `mia-whatsapp` (`python scripts/servicios.py encender MIA mia-whatsapp --forzar`); sin migraciones. El comportamiento no cambia mientras `BOT_CLARIFY=off`.
3. Poner `BOT_CLARIFY=on` y `BOT_CLARIFY_MIN_SIMILARITY` (el calibrado) en la API (variables de Railway, desplegar) y probar desde el teléfono de prueba: "¿Cuándo empiezan las lecciones?", contestar el programa, y una pregunta con el programa nombrado (debe responder igual que hoy).
4. Revisar en Uso que el costo por pregunta del bot sigue en el orden de 0,0004 USD y en los registros del servicio la proporción de `aclaracion`.

**Volver atrás**: `BOT_CLARIFY=off` en la API (y reiniciar) devuelve el comportamiento anterior sin tocar el servicio; el contexto del servicio no cambia ninguna respuesta por sí solo (sin aclaración ni programa que recordar, el flujo es el de hoy).
