# Contrato: citas del modelo y fuentes de la respuesta

No cambia ningún endpoint ni el esquema de la API. Este documento fija los tres acuerdos nuevos: el formato del contexto y de la línea de citas (entre la API y el modelo), la regla de selección de fuentes, y la variable de configuración.

## 1. Contexto entregado al modelo

Con la opción **apagada**, cada pasaje se entrega exactamente como hoy:

```text
[Fuente: dominio=<dominio>, documento=<documento>]
<texto del pasaje>
```

Con la opción **encendida**, cada pasaje lleva su número (de 1 a N, en el orden de entrega):

```text
[Fuente <n>: dominio=<dominio>, documento=<documento>]
<texto del pasaje>
```

Los pasajes se separan por una línea en blanco, igual que hoy. La instrucción de sistema del modo (literal o razonamiento) se mantiene y, encendida la opción, se le agrega al final un párrafo con este contenido (redacción final en el código; debe mantenerse corto):

> Después de tu respuesta, en una última línea aparte, escribe `FUENTES:` seguido de los números de los fragmentos que realmente usaste, separados por comas (por ejemplo: `FUENTES: 1, 3`). Cita solo los fragmentos de los que tomaste información; no cites todos los que recibiste. No uses estos números dentro del texto de la respuesta. Si respondes SIN_INFORMACION, no escribas esa línea.

## 2. Interpretación de la respuesta del modelo (con la opción encendida)

| Caso de la respuesta | Texto devuelto | Fuentes listadas | Regla de seguridad |
|---|---|---|---|
| Última línea `FUENTES: 1, 3`, ambos entre 1 y N | sin la línea | pasajes 1 y 3 | no |
| `FUENTES: 3, 3, 1` | sin la línea | pasajes 1 y 3 (orden original, sin repetir) | no |
| `FUENTES: 2, 9` con N = 4 | sin la línea | pasaje 2 | no |
| `FUENTES: 9, 12` con N = 4 | sin la línea | todos | **sí** |
| `FUENTES: ninguna` o sin números | sin la línea | todos | **sí** |
| Sin línea de citas | original | todos | **sí** |
| `**FUENTES:** 2` (con Markdown) o `fuentes: 2` | sin la línea | pasaje 2 | no |
| `FUENTES:` en medio del texto, no al final | original | todos | **sí** |
| Texto limpio igual a `SIN_INFORMACION` (con o sin la línea de citas) | respuesta fija de "sin información" | ninguna | no aplica |
| Respuesta cortada antes de la línea | original | todos | **sí** |

Cómo se reconoce la línea: es la última línea no vacía; tras quitar signos de Markdown (`*`, `_`, `#`, `>`) y espacios, empieza por `fuentes:` o `fuente:` sin distinguir mayúsculas ni tildes. Los números son los enteros que aparecen en ella.

Con la opción **apagada**: no se pide la línea, no se interpreta nada y el texto, las fuentes y el registro son idénticos a los de antes de la feature (si el modelo escribiera por su cuenta una línea `FUENTES:`, se deja como está, como hoy).

## 3. Respuesta de la API

Misma estructura de siempre. `answer` es el texto limpio; `sources` es la lista filtrada (cada elemento `{domain, document, excerpt}`), nunca vacía en una respuesta con contenido; `no_info` y los demás campos no cambian. La Consulta administrativa y `scripts/pruebas_mvp.py` no necesitan cambios.

## 4. Registro de Uso

- `sources`: documentos de la lista filtrada, sin repetidos.
- `reject_reason`: nota `Fuentes: sin citas utilizables, se mostraron todas` solo en consultas respondidas en las que rigió la regla de seguridad. El panel de Uso la muestra junto al resultado y el CSV la incluye.
- Costo, tokens y latencia: se registran como siempre.

## 5. Configuración

| Variable | Valores | Defecto |
|---|---|---|
| `QUERY_CITED_SOURCES` | `on`, `true`, `1`, `yes` encienden; `off`, `false`, `0`, `no` o vacío apagan; otro valor se trata como apagado y deja un aviso en el registro del servidor | `off` |

Cambiarla en Railway y reiniciar el servicio basta; no hay migración ni despliegue de código.

## 6. Cambios a la herramienta de la feature 005

- `respuestas` registra, por consulta, `regla_de_seguridad` (a partir del `reject_reason` del detalle de Uso) y el resumen por modo la cuenta y da su proporción.
- `informe` y `comparar` muestran ese dato y las diferencias de fuentes mostradas entre dos corridas.
- No cambian los códigos de salida ni las demás opciones.
