# Modelo de datos: Pregunta limpia

Sin tablas ni columnas nuevas: no hay migraciones y los documentos no se reindexan.

## Configuración (`src/mia/config.py`, `.env.example`)

| Variable | Tipo | Por defecto | Validación |
|---|---|---|---|
| `QUERY_CLEAN_QUESTION` | texto | `off` | `on`/`off`; cualquier otro valor se trata como `off` con un aviso (una vez) |

## Registro de consultas (`QueryLog`, tabla existente)

`reject_reason` (texto, hasta 500 caracteres, ya existente) lleva la nota de la pregunta limpia cuando la hubo, unida con "; " a las notas de las features 006 y 007.

| Nota | Cuándo |
|---|---|
| `Pregunta limpia: «<texto>» (con resultados)` | Hubo segundo intento y algún fragmento superó el umbral. |
| `Pregunta limpia: «<texto>» (sin resultados)` | Hubo segundo intento y ningún fragmento superó el umbral. La consulta termina en `no_info`. |

El texto se recorta a 120 caracteres para no acercarse al límite de la columna junto con las otras notas. Las consultas sin segundo intento no cambian.

## Entidades del módulo `query_rewrite` (sin persistencia)

| Entidad | Campos | Notas |
|---|---|---|
| Pregunta limpia | texto (`str`) | Resultado de `clean_question`; `None` si no corresponde. No se guarda salvo dentro de la nota de Uso. |
| Nota de pregunta limpia | texto (`str`) | Construida por `clean_note(text, found)`. |

## Casos de la herramienta (`scripts/datos/casos_busqueda.json`)

Campos nuevos opcionales:

| Campo | Tipo | Significado |
|---|---|---|
| `sin_pregunta_limpia` | bool | El caso es un negativo: la API no debe hacer segundo intento con él. |

Categoría nueva `envoltura`: la misma pregunta de identificación de un caso existente con otras redacciones, con el mismo `documentos` esperado. Sin otros campos nuevos: el informe usa `espera`, `documentos` y los campos de las features 005 a 007.
