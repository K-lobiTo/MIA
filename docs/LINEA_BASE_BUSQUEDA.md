# Línea base de la búsqueda de MIA

Generado de la corrida `base` por `scripts/linea_base.py` (feature [005](../specs/005-linea-base-busqueda/spec.md)). No contiene texto de fragmentos ni de respuestas.

## Contexto de la corrida

- Fecha: 2026-10-15T21:58:56-06:00
- Commit: `09fc26aac4` (con cambios sin confirmar)
- Destino: produccion
- Umbral de similitud declarado: 0.82
- Resultados de búsqueda por modo: literal 8, razonamiento 16
- Candidatos pedidos por pregunta: 50
- Embeddings: local (dimensión 384)
- Fragmentos por dominio: Unidad de Postgrados de Computación / Apertura de promoción: 0; Unidad de Postgrados de Computación / Currículum: 1723; Unidad de Postgrados de Computación / Docentes: 0; Unidad de Postgrados de Computación / Memoria del Consejo: 429; Unidad de Postgrados de Computación / Proyectos de graduación: Artículos: 853; Unidad de Postgrados de Computación / Proyectos de graduación: Informes de IPA: 755; Unidad de Postgrados de Computación / Proyectos de graduación: Tesis: 1918; Área académica de Analítica de Negocios / Apertura de promoción: 0; Área académica de Analítica de Negocios / Currículum: 505; Área académica de Analítica de Negocios / Docentes: 0; Área académica de Analítica de Negocios / Memoria del Consejo: 56

## Resultados por caso

| Caso | Categoría | Espera | Mejor puntaje | Posición esperado | Literal (retrieval) | Razonamiento (retrieval) | Literal: correcto / sobrantes / s / USD | Razonamiento: correcto / sobrantes / s / USD |
|---|---|---|---|---|---|---|---|---|
| A1 | mvp | respuesta | 0.875 | 1 | responde | responde | sí / 1 / 3.0 / 0.0009 | sí / 2 / 5.7 / 0.0031 |
| A2 | mvp | respuesta | 0.879 | 2 | responde | responde | sí / 1 / 1.7 / 0.0001 | sí / 2 / 3.8 / 0.0010 |
| A3 | mvp | respuesta | 0.903 | 1 | responde | responde | sí / 2 / 3.1 / 0.0010 | sí / 3 / 7.0 / 0.0069 |
| U1 | mvp | respuesta | 0.906 | 1 | responde | responde | sí / 5 / 2.0 / 0.0016 | sí / 9 / 8.7 / 0.0019 |
| U2 | mvp | respuesta | 0.912 | 1 | responde | responde | sí / 3 / 1.7 / 0.0012 | sí / 6 / 4.8 / 0.0024 |
| U3 | mvp | respuesta | 0.876 | 1 | responde | responde | sí / 1 / 1.7 / 0.0006 | sí / 1 / 2.8 / 0.0013 |
| U4 | mvp | respuesta | 0.859 | 1 | responde | responde | sí / 3 / 2.6 / 0.0013 | sí / 4 / 5.4 / 0.0027 |
| P1 | mvp | respuesta | 0.871 | 2 | responde | responde | sí / 4 / 1.8 / 0.0014 | sí / 6 / 2.5 / 0.0195 |
| P2 | mvp | respuesta | 0.888 | 4 | responde | responde | sí / 2 / 1.4 / 0.0008 | sí / 4 / 4.7 / 0.0075 |
| K1 | mvp | respuesta | 0.890 | 1 | responde | responde | sí / 2 / 1.6 / 0.0007 | sí / 5 / 2.9 / 0.0165 |
| K2 | mvp | respuesta | 0.900 | 1 | responde | responde | sí / 3 / 2.6 / 0.0009 | sí / 4 / 7.2 / 0.0044 |
| CU1 | mvp | respuesta | 0.900 | 1 | responde | responde | sí / 0 / 4.5 / 0.0013 | sí / 0 / 12.7 / 0.0054 |
| G1 | mvp | respuesta | 0.886 | 1 | responde | responde | sí / 0 / 2.2 / 0.0009 | sí / 0 / 2.7 / 0.0129 |
| G2 | mvp | respuesta | 0.905 | 1 | responde | responde | sí / 0 / 5.0 / 0.0008 | sí / 0 / 4.4 / 0.0125 |
| N1 | mvp | sin_informacion | 0.799 | - | sin_informacion | sin_informacion | sí / 0 / 0.5 / 0.0000 | sí / 0 / 0.4 / 0.0000 |
| X1 | mvp | respuesta | 0.871 | 2 | responde | responde | sí / 4 / 1.7 / 0.0014 | sí / 6 / 2.5 / 0.0199 |
| I1 | mvp | sin_informacion | 0.846 | - | responde | responde | sí / 0 / 1.1 / 0.0010 | sí / 0 / 1.8 / 0.0205 |
| I3 | mvp | sin_informacion | 0.852 | - | responde | responde | sí / 0 / 1.3 / 0.0008 | sí / 0 / 2.3 / 0.0031 |
| I2 | mvp | sin_informacion | 0.799 | - | sin_informacion | sin_informacion | sí / 0 / 0.4 / 0.0000 | sí / 0 / 0.4 / 0.0000 |
| S22-1 | seccion_2_2 | respuesta | 0.798 | 3 | sin_informacion | sin_informacion | NO / 0 / 0.5 / 0.0000 | NO / 0 / 0.4 / 0.0000 |
| S22-1 (corta) | seccion_2_2 | respuesta | 0.833 | 12 | responde | responde | NO / 0 / 1.5 / 0.0001 | sí / 9 / 3.4 / 0.0030 |
| S22-2 | seccion_2_2 | respuesta | 0.873 | ausente | responde | responde | NO / 4 / 3.1 / 0.0009 | NO / 5 / 9.6 / 0.0053 |
| S22-2 (corta) | seccion_2_2 | respuesta | 0.850 | 2 | responde | responde | sí / 1 / 5.1 / 0.0011 | sí / 2 / 5.9 / 0.0024 |
| S22-3 | seccion_2_2 | respuesta | 0.775 | ausente | sin_informacion | sin_informacion | NO / 0 / 0.5 / 0.0000 | NO / 0 / 0.5 / 0.0000 |
| S22-3 (corta) | seccion_2_2 | respuesta | 0.807 | 15 | sin_informacion | sin_informacion | NO / 0 / 0.5 / 0.0000 | NO / 0 / 0.6 / 0.0000 |
| S22-4 | seccion_2_2 | respuesta | 0.802 | 19 | sin_informacion | sin_informacion | NO / 0 / 0.7 / 0.0000 | NO / 0 / 0.4 / 0.0000 |
| S22-4 (corta) | seccion_2_2 | respuesta | 0.827 | 3 | responde | responde | NO / 0 / 1.1 / 0.0002 | NO / 0 / 1.0 / 0.0002 |
| IN1 | indirecta | respuesta | 0.884 | 2 | responde | responde | sí / 4 / 2.4 / 0.0014 | sí / 8 / 6.4 / 0.0035 |
| IN2 | indirecta | respuesta | 0.882 | 2 | responde | responde | sí / 3 / 1.6 / 0.0009 | sí / 9 / 11.2 / 0.0317 |
| IN3 | indirecta | respuesta | 0.838 | 1 | responde | responde | sí / 1 / 3.3 / 0.0008 | sí / 2 / 6.2 / 0.0056 |
| SG1 | sigla | respuesta | 0.873 | 6 | responde | responde | sí / 3 / 3.8 / 0.0011 | sí / 3 / 6.0 / 0.0034 |
| SG2 | sigla | respuesta | 0.904 | 2 | responde | responde | sí / 2 / 2.0 / 0.0008 | sí / 6 / 3.6 / 0.0018 |
| SG3 | sigla | respuesta | 0.900 | ausente, 38 | responde | responde | NO / 1 / 2.8 / 0.0010 | NO / 1 / 7.2 / 0.0050 |
| SR1 | sin_respuesta | sin_informacion | 0.820 | - | sin_informacion | sin_informacion | sí / 0 / 0.5 / 0.0000 | sí / 0 / 0.4 / 0.0000 |
| SR2 | sin_respuesta | sin_informacion | 0.827 | - | responde | responde | sí / 0 / 1.4 / 0.0009 | sí / 0 / 1.5 / 0.0006 |
| SR3 | sin_respuesta | sin_informacion | 0.839 | - | responde | responde | sí / 0 / 1.9 / 0.0009 | sí / 0 / 2.4 / 0.0208 |

## Ventana de separación (BUS-3)

- Mayor mejor puntaje entre los casos que esperan "sin información": 0.852 (caso I3).
- Sin contar los casos de aislamiento de dominio: 0.839 (caso SR3).
- Menor puntaje del documento esperado entre los casos que esperan respuesta: 0.781 (caso S22-4).
- ¿Algún umbral separa ambos grupos?: no.
- Casos cuyo documento esperado no aparece entre los candidatos: S22-2, S22-3.

## Pregunta completa frente a variante corta

| Caso | Completa | Distancia al umbral | Corta | Distancia al umbral |
|---|---|---|---|---|
| S22-1 | 0.798 | -0.022 | 0.833 | 0.013 |
| S22-2 | 0.873 | 0.053 | 0.850 | 0.030 |
| S22-3 | 0.775 | -0.045 | 0.807 | -0.013 |
| S22-4 | 0.802 | -0.018 | 0.827 | 0.007 |

## Barrido de umbrales

Modo literal (casos cuyo resultado cambia frente a 0.82):

| Umbral | Pasan a responder | Pasan a "sin información" |
|---|---|---|
| 0.60 a 0.77 | N1, I2, S22-1, S22-3, S22-4, SR1 | - |
| 0.78 a 0.79 | N1, I2, S22-1, S22-4, SR1 | - |
| 0.80 | S22-4, SR1 | - |
| 0.81 | SR1 | - |
| 0.83 | - | SR2 |
| 0.84 | - | IN3, SR2, SR3 |
| 0.85 | - | I1, IN3, SR2, SR3 |
| 0.86 a 0.87 | - | U4, I1, I3, IN3, SR2, SR3 |
| 0.88 | - | A1, A2, U3, U4, P1, X1, I1, I3, S22-2, IN3, SG1, SR2, SR3 |
| 0.89 | - | A1, A2, U3, U4, P1, P2, G1, X1, I1, I3, S22-2, IN1, IN2, IN3, SG1, SR2, SR3 |
| 0.90 | - | A1, A2, U3, U4, P1, P2, K1, CU1, G1, X1, I1, I3, S22-2, IN1, IN2, IN3, SG1, SG3, SR2, SR3 |

Modo razonamiento (casos cuyo resultado cambia frente a 0.82):

| Umbral | Pasan a responder | Pasan a "sin información" |
|---|---|---|
| 0.60 a 0.77 | N1, I2, S22-1, S22-3, S22-4, SR1 | - |
| 0.78 a 0.79 | N1, I2, S22-1, S22-4, SR1 | - |
| 0.80 | S22-4, SR1 | - |
| 0.81 | SR1 | - |
| 0.83 | - | SR2 |
| 0.84 | - | IN3, SR2, SR3 |
| 0.85 | - | I1, IN3, SR2, SR3 |
| 0.86 a 0.87 | - | U4, I1, I3, IN3, SR2, SR3 |
| 0.88 | - | A1, A2, U3, U4, P1, X1, I1, I3, S22-2, IN3, SG1, SR2, SR3 |
| 0.89 | - | A1, A2, U3, U4, P1, P2, G1, X1, I1, I3, S22-2, IN1, IN2, IN3, SG1, SR2, SR3 |
| 0.90 | - | A1, A2, U3, U4, P1, P2, K1, CU1, G1, X1, I1, I3, S22-2, IN1, IN2, IN3, SG1, SG3, SR2, SR3 |

## Respuesta completa

- Corrida del 2026-10-15T22:12:18-06:00 contra produccion, artefacto "PRUEBA Aceptación ambas unidades", modos literal, razonamiento, tope de la corrida 0.4 USD, gasto 0.2514 USD.

### Modo literal

- Consultas: 36; correctos: 28; fallidos: S22-1, S22-1, S22-2, S22-3, S22-3, S22-4, S22-4, SG3; no concluyentes: ninguno.
- Fuentes sobrantes promedio: 1.39.
- Latencia p50 / p95: 1694 ms / 4953 ms.
- Costo medio por consulta: 0.000744 USD; el de las que terminan en "sin información": 0.000306 USD.
- Gasto total: 0.0268 USD.

### Modo razonamiento

- Consultas: 36; correctos: 29; fallidos: S22-1, S22-2, S22-3, S22-3, S22-4, S22-4, SG3; no concluyentes: ninguno.
- Fuentes sobrantes promedio: 2.69.
- Latencia p50 / p95: 3381 ms / 11214 ms.
- Costo medio por consulta: 0.006241 USD; el de las que terminan en "sin información": 0.003767 USD.
- Gasto total: 0.2247 USD.

## Lectura

Escrita a mano el 2026-10-15 a partir de las tablas anteriores (corrida `base`: puntajes y respuestas contra producción, 32 casos y 36 preguntas por modo con las variantes cortas). Es la lectura de los números, no una decisión: las decisiones son de la sección 2.8 de [Definicion_Requerimientos_V3.md](Definicion_Requerimientos_V3.md). Si se regenera el informe con `informe --salida`, esta sección se conserva.

### Lo que hoy funciona

- Los 19 casos de la batería del MVP responden bien en los dos modos. Los 4 que esperan "sin información" lo logran, pero no por igual: `N1` e `I2` (mejor puntaje 0,799) se cortan por el umbral sin llamar al modelo y cuestan 0; `I1` (0,846) e `I3` (0,852) **sí superan el umbral** y es el modelo el que dice "sin información" (cuestan entre 0,0008 y 0,0205 USD).
- Las preguntas indirectas (`IN1` a `IN3`) y con sigla `SG1` y `SG2` responden bien. El documento esperado queda entre los 6 primeros candidatos.

### Lo que hoy falla (los 8 casos de BUS-1 y BUS-2)

- **Nombre y apellidos (`S22-1`, `S22-3`, `S22-4`):** con la pregunta completa el mejor puntaje es 0,775 a 0,802, bajo el umbral, y responde "sin información" en 0,4 a 0,7 s sin llamar al modelo. Con solo el nombre sube a 0,807 a 0,833: dos de las tres pasan el umbral, pero `S22-3` no, y en `S22-4` el documento esperado queda en el puesto 3 con 0,819, 0,001 bajo el umbral, así que tampoco llega al modelo.
- **Sigla frente a forma desarrollada (`S22-2`):** con la pregunta larga el documento "Líneas de TFG" **no aparece entre los 50 candidatos** y el modelo responde con otros 4 documentos (respuesta que no cita lo esperado). Con "TFG" queda en el puesto 2.
- **Sigla de la maestría (`SG3`, "MGTI"):** responde con un documento que no es el esperado; "Plan 473" no aparece entre los 50 candidatos y el otro documento esperado queda en el puesto 38.

### Ventana de separación (BUS-3)

No hay un umbral que separe los casos con respuesta de los que no la tienen: el mayor puntaje entre los "sin información" es 0,852 (`I3`; 0,839 sin contar los de aislamiento de dominio) y el menor puntaje de un documento esperado es 0,781 (`S22-4`). Solo con la batería original sí existía una ventana (0,852 a 0,859), pero muy estrecha. Consecuencias por opción:

- **A, bajar el umbral:** no es viable. Para recuperar `S22-1` (0,798) hay que bajar a 0,79 o menos, y entonces dejan de cortarse `N1`, `I2` y `SR1`, que no tienen respuesta (el barrido de umbrales lo detalla); para `S22-3` (0,775) habría que bajar a 0,77.
- **C, umbral distinto por modo:** el barrido sale idéntico en los dos modos (la decisión de responder depende del mejor candidato, que es el mismo; el modo solo cambia cuántos fragmentos pasan), así que un umbral por modo no cambia qué casos responden.
- **B, segundo intento con pregunta limpia:** ayuda a las personas, porque la variante corta sube entre 0,025 y 0,035 sobre la completa, pero no alcanza sola: `S22-3` sigue bajo el umbral, y en `S22-1` el documento está en el puesto 12 con 0,824, así que el modo literal (que ve 8 resultados) no lo recibe y solo el de razonamiento (16) acierta. No resuelve las siglas.
- **E, reranker:** el documento esperado aparece entre los 50 candidatos en todos los casos salvo `S22-2` (pregunta larga), `S22-3` (pregunta larga) y `SG3` (uno de los dos). Con 20 candidatos entran las variantes cortas de las tres personas (puestos 3 a 15) y las preguntas completas `S22-1` y `S22-4` (puestos 3 y 19); con 40 también `SG3` (puesto 38). Un corte por puntaje del reranker sustituiría al umbral de similitud, que no discrimina.
- **D, búsqueda híbrida:** los fallos que quedan (sigla "TFG", sigla "MGTI", nombres propios) son de coincidencia exacta de términos, que es lo que aporta BM25.

### Fuentes mostradas (BUS-5)

Contra los documentos que marqué como esperados por caso (una sola persona los marcó, así que un documento extra puede haber aportado y contarse como sobrante), la respuesta lista en promedio **1,39 fuentes sobrantes en modo literal y 2,69 en razonamiento**, con casos de 9 y 10 fuentes para 1 esperada (`U1`, `IN2`, `S22-1` corta en razonamiento). Los casos de un solo documento (`G1`, `G2`) y `CU1` no tienen sobrantes.

### Latencia y costo

| | Literal | Razonamiento |
|---|---|---|
| Latencia p50 / p95 del cliente | 1,7 s / 5,0 s | 3,4 s / 11,2 s |
| Costo medio por consulta | 0,00074 USD | 0,00624 USD |
| Costo medio de las que terminan en "sin información" | 0,00031 USD | 0,00377 USD |
| Una "sin información" cortada por umbral | 0 | 0 |
| Una "sin información" decidida por el modelo | 0,0008 a 0,0010 USD | 0,0006 a 0,0208 USD |

La corrida completa (72 consultas) costó **0,2514 USD** y coincide con el aumento del total de Uso del artefacto en esa ventana (0,2514 USD). La comprobación independiente se hizo el mismo día en OpenRouter *Activity*: 0,242 USD en GLM 5.3 (modo razonamiento) y 0,27 USD en total con el modelo Flash (modo literal). Ese total equivale a la corrida (0,2514) más una prueba previa de tres casos del mismo día (0,0187), 0,2701 USD en el módulo Uso: diferencia menor al 1 %. Con eso se cerró también el criterio 15 de V2.

### Datos para las decisiones de la sección 2.8 de V3

1. **Gasto extra por consulta sin respuesta:** hoy una consulta sin respuesta cuesta 0 si la corta el umbral, y entre 0,0008 y 0,02 USD si pasa al modelo. Un segundo intento (B) agrega a lo sumo una búsqueda local por consulta que no pasa el umbral; el reranker local no agrega costo de modelos.
2. **Límites de memoria y latencia:** la latencia actual (arriba) es la vara; la memoria no se midió en esta línea base.
3. **Medir en producción:** resuelta, se midió en solo lectura (el usuario declaró públicos los datos para pruebas).
4. **Qué modelo de reranker probar:** sin datos nuevos; el dato útil es que bastan unos 20 a 40 candidatos.
5. **Cuántos casos:** el conjunto actual (32 casos, 36 preguntas por modo) alcanza para ver el patrón; faltan más casos de siglas y de pregunta indirecta con respuesta dudosa para calibrar un corte por puntaje.

## Resultado de la feature 006 (fuentes que aportaron)

Medido el 2026-10-16 en producción con el código de `dev` (commit `59ee6c9`), mismos 32 casos y 36 preguntas por modo que la línea base. Tres corridas: `base` (código anterior, 2026-10-15), `control` (código nuevo con `QUERY_CITED_SOURCES=off`) y `citas` (código nuevo con la opción en `on`). El control sirve para comprobar que apagada no cambia nada y para estimar el ruido entre corridas. Gasto: control 0,127 USD y citas 0,183 USD.

| Criterio | Meta | Resultado | Veredicto |
|---|---|---|---|
| SC-001 fuentes que no aportaron por consulta | bajar al menos 50 % | literal 1,28 (control) a 0,28 (-78 %); razonamiento 2,69 a 0,47 (-82 %). Contra `base`: 1,39 a 0,28 y 2,69 a 0,47 | Cumple |
| SC-002 batería del MVP | los 19 casos bien y su documento esperado | 30 de 30 consultas de los 15 casos que esperan respuesta correctas (15 casos por 2 modos) y los 4 de "sin información" correctos | Cumple |
| SC-003 "sin información" | los mismos casos | el resultado (respondió, sin información) es idéntico al control en las 72 consultas | Cumple |
| SC-004 costo medio | no sube más de 5 % | literal: 0,00076 USD frente a 0,00074 (base) y 0,00077 (control), mediana de la razón por caso 1,009 frente a `base` y 0,993 frente al control. Razonamiento: 0,00432 USD frente a 0,00624 (base) y 0,00277 (control), que ya difieren 2,3 veces entre sí; mediana de la razón 0,922 frente a `base` y 1,175 frente al control; los tokens totales medianos casi no cambian (11.143 a 11.231, +0,8 %) | Cumple en literal. En razonamiento el costo no se puede separar del ruido de la medición (rango por caso de 0,3 a 9,9 veces); los tokens, que son más estables, suben menos de 1 % |
| SC-005 latencia p50 | no sube más de 10 % | literal 1.695 ms frente a 1.694 (base) y 1.760 (control). Razonamiento 3.346 ms frente a 3.381 (base) y 2.625 (control): mediana de la razón 0,899 frente a `base` y 1,086 frente al control | Cumple en literal; en razonamiento queda dentro del ruido (base y control difieren 29 % entre sí) |
| SC-006 regla de seguridad | 10 % o menos | 1 de 46 respuestas con contenido (2,2 %): `X1` en literal; en razonamiento ninguna | Cumple |
| SC-007 nunca sin fuentes | ninguna respuesta con contenido sin fuentes | ninguna | Cumple |
| SC-008 apagada no cambia nada | cero diferencias de documentos mostrados | `base` contra `control`: una sola diferencia, `S22-2` en literal (respondió con 4 fuentes en una corrida y "sin información" en la otra, variación del modelo); los demás documentos mostrados son idénticos | Cumple |
| SC-009 verificación por una persona | 3 respuestas | el usuario hizo la comprobación con tres preguntas reales (ver abajo); no emitió un veredicto formal de "sí" o "no" por pregunta, solo observaciones | Cumple según la lectura del asistente, sin veredicto formal del usuario |

**Fuentes que siguen apareciendo de más** (sobre los documentos marcados por una sola persona, así que algunos pueden haber aportado de verdad): `A1` y `IN3` muestran además el acta 03-2026; `K2` el acta CUP_001-2025; `X1` en literal cuatro documentos de Ciberseguridad (el caso es multi-programa); `SG1` y `P2` e `IN2` el plan de estudios de Ciberseguridad; `U1`, `U2`, `U4` y `SG2` el documento final del programa o el de IPA en Big Data. Quedan a validación del usuario.

**Un incidente de la medición, que conviene recordar:** la primera corrida con la opción encendida no midió nada, porque cambiar una variable con `railway variable set` (sin `--skip-deploys`) hace que Railway **redespliegue desde la rama `main` de GitHub y no desde el código subido con `railway up`**: el servicio volvió a correr el código anterior sin que ningún mensaje lo avisara. Se detectó porque los tokens por consulta eran idénticos a los del control y los metadatos del despliegue mostraban el commit de `main`. La corrida se descartó (quedó guardada como `...-citas-invalida-codigo-main`, 0,09 USD) y se repitió cambiando la variable con `--skip-deploys` y redesplegando con `servicios.py encender --ref origin/dev`. Ver OPERACION.md.

**Validación manual de SC-009 (2026-10-16)**, con la opción encendida y el artefacto de prueba, en modo literal:

| Pregunta | Fuentes listadas | Lectura |
|---|---|---|
| Contenidos del curso Diseño de Experimentos (dos redacciones) | `MC6104 Diseño de Experimentos.pdf`; en la redacción más corta también `Reforma curricular MC-CC.pdf` | Cada fuente respalda algo de la respuesta: MC6104 el temario y la reforma la frase sobre estadística y análisis de varianza. Se descartaron 4 o 5 documentos que la búsqueda había entregado (catálogo de cursos, MC-6105, plan de Ciberseguridad). El temario salió incompleto (llega a B.10) por el tamaño del pasaje, algo independiente de esta opción |
| Blockchain y pagos descentralizados (dominios currículum y proyectos) | `MC4001- Blockchain y Ladger Distribuidos.docx`, la tesis de Luis Alvarado Gómez (2 pasajes) y `Plan de Estudios Maestría en Ciberseguridad v3.2.docx` | Los dos documentos esperados aparecen. El plan de estudios solo corrobora lo que ya dice MC4001: es redundante, no incorrecto. De 8 pasajes entregados se listaron 4 |
| Presupuesto del programa (Memoria del Consejo) | Actas N°19, N°10 (consulta formal), N°14 y N°15 de 2025 | Cada acta respalda una afirmación distinta (presupuesto de Ciberseguridad 2026, tope de ¢550.000 para internacionalización, presupuesto de infraestructura de IA, borrador de presupuesto para el INDER). El Acta 17, también candidata, no se listó |

Un intento con una pregunta de plazos de tesis respondió "sin información" y sin fuentes, como corresponde cuando ninguna acta trata el tema. Repetida 7 veces, la pregunta de las becas (IN3, modo literal) mostró una sola fuente (Acta 04-2026) en 5 de 7 corridas; en 2 aplicó la regla de seguridad (una de ellas con la respuesta cortada a media frase por el proveedor), así que en una pregunta concreta la regla puede aplicarse mucho más que el 2 % medido en general.

**Criterio del usuario sobre los sobrantes (2026-10-16):** para las fuentes que siguen apareciendo de más (arriba) dijo que no hace falta validarlas una por una: prefiere que sobren referencias a que falten. Solo validó dos filas (`A1` e `IN3`: el Acta 03-2026 no tiene relación), que quedan contadas como sobrantes. El resto se cuenta como sobrante en el resultado, así que el -80 % es una cota prudente.

**Recomendación:** la opción reduce las fuentes que no aportaron en alrededor de 80 % sin cambiar ninguna respuesta ni subir el costo ni la latencia de forma medible, y la regla de seguridad se aplicó en el 2 % de las respuestas. Es seguro encenderla. La decisión de dejarla encendida por defecto es del usuario; apagada sigue siendo el valor por defecto de la configuración.

## Resultado de la feature 007 (respuestas completas, sin cortes)

Medido el 2026-10-18 en producción con el código de `dev`, 45 consultas por modo (los 32 casos y sus variantes más 9 casos nuevos de listas largas, `LL1` a `LL9`). Cuatro corridas: `control7` (opciones de la 007 apagadas y citas de la 006 apagadas), `completo` (`QUERY_COMPLETE_CONTEXT=on`), `completo-reintento` (además `QUERY_RETRY_CUT_ANSWERS=on`) y `todo` (esas dos más `QUERY_CITED_SOURCES=on`, que es la configuración de producción prevista). Gasto: 0,158, 0,186, 0,124 y 0,146 USD.

| Criterio | Resultado | Veredicto |
|---|---|---|
| SC-001 listas largas completas (criterio ajustado el 2026-10-18: cuentan las listas cuyo documento llega al modelo y cabe en 25 fragmentos; la recuperación y los documentos enormes se reportan aparte) | `LL1` (Diseño de Experimentos, el caso que originó la feature) pasó de cortada a completa en los dos modos. `LL3` a `LL8` (PLN, Redes Neuronales, Introducción a la Investigación, Sistemas Operativos Avanzados, lista del acta 04-2026, criterios del reglamento) ya salían completas sin la feature. `LL2` (Deep Learning) falla antes y después por **recuperación, no por contexto**: el programa MC8840 aparece en el puesto 50 de la búsqueda con esa pregunta (en el 14 aun con el código del curso, detrás del catálogo de cursos) y nunca llega al modelo. `LL9` (plan de estudios de Ciberseguridad, 309 fragmentos) no puede salir completa; la respuesta con la opción dice "La lista puede continuar en ese documento (...)" y en razonamiento "no contienen la lista completa", que es lo que pide FR-004 | 7 de 8 listas comparables; la octava es un problema de búsqueda ajeno a la feature. FR-004 cumple en el caso del documento enorme |
| SC-002 ninguna respuesta cortada sin aviso | Ningún fin anormal en la medición: 76 de 76 llamadas al modelo de la corrida `todo` terminaron en `stop` según el log del servidor, y 0 reintentos y 0 avisos en las corridas con la opción. El mecanismo está probado solo con pruebas automáticas (reintento, tope de gasto, dos cortes, fallo del segundo intento y combinación con las citas) | No hubo cortes que atender; no se ejercitó en producción (ver el límite de la verificación abajo) |
| SC-003 batería del MVP y "sin información" | Los casos de la batería dan el mismo resultado en `control7`, `completo`, `completo-reintento` y `todo`; las únicas diferencias entre corridas son las de variación del modelo (`S22-2`, que también variaba entre `base` y `control`) | Cumple |
| SC-004 reintentos | 0 de 90 consultas con la opción encendida | Cumple (0 %) |
| SC-005 costo medio | Mediana de la razón por caso frente a `control7`: **literal 1,22** con contexto completo y 1,15 con el reintento encendido; **razonamiento 1,19 y 1,01**. Tokens medianos por consulta: literal 5.652 a 7.074 (+25 %), razonamiento 10.327 a 12.458 (+21 %). Costo medio: literal 0,00068 a 0,00082 USD (+21 %), razonamiento 0,00282 a 0,00333 (+18 %), con mucho ruido entre corridas | Dentro del 25 %, **pero en literal con muy poco margen**: el aumento de tokens es de 25 % |
| SC-006 latencia p50 | literal 2.378 ms (control7) frente a 2.175 y 1.900; razonamiento 2.856 frente a 3.007 y 2.819 | Cumple |
| SC-007 apagadas, mismo resultado que la línea base | `base` contra `control7`: 6 diferencias, todas de variación del modelo en `S22-2` y en el conteo de casos nuevos | Cumple |
| SC-008 regla de seguridad con la 006 | `todo`: 1 respuesta en literal y 1 en razonamiento de 70 con contenido (menos de 3 %) | Cumple |
| SC-009 verificación por una persona | el 2026-10-18 el usuario consultó en modo literal, con las tres opciones encendidas, los contenidos de Diseño de Experimentos, Procesamiento de Lenguaje Natural e Introducción a la Investigación: las tres respuestas salieron completas, y observó que incluso señalaban inconsistencias en los propios documentos originales | Cumple |

**Límite de la verificación de SC-002.** La medición no produjo ningún fin anormal, así que el reintento y el aviso están probados solo con pruebas automáticas (`tests/unit/test_query_completeness.py` y `tests/unit/test_completeness.py`). Si se quisiera ejercitarlos en producción, la forma es provocar el corte: en una instancia de prueba, bajar `OPENROUTER_MAX_TOKENS` hasta un valor muy pequeño (por ejemplo 50) con `QUERY_RETRY_CUT_ANSWERS=on`, preguntar por un temario y comprobar la nota `Respuesta cortada: se entregó con aviso` en el módulo Uso y el aviso al final del texto; restaurar el valor al terminar.

**Hallazgos aparte de la feature**
- La mayoría de las listas de programas de curso (5 de 6) ya salían completas sin la feature: el temario cabía en el fragmento y su vecino. El caso que falló, Diseño de Experimentos, tiene 15 fragmentos justo por encima del límite de 12 para entregar un documento completo. La feature resuelve ese caso y deja un margen para los programas de hasta 25 fragmentos.
- Un documento que contiene la respuesta puede no llegar al modelo si otro documento parecido (el catálogo de cursos) puntúa más (`LL2`). Eso es del dominio de las opciones B, D y E de V3.
- El registro `Fin de la generación: ...` no se veía en Railway porque Python solo muestra WARNING; se corrigió en `mia.api.main` (hasta el 2026-10-18 los mensajes informativos del servidor no salían).
- La métrica "termina sin puntuación" sobrestima los cortes: las respuestas que terminan en el último ítem de una lista sin punto (por ejemplo "Varios" o "Cloud Computing") se cuentan aunque estén completas. Sirve de alarma, no de contador.

**Recomendación:** encender `QUERY_COMPLETE_CONTEXT` resuelve el caso que motivó la feature pero cuesta cerca de +20 % en tokens (literal 25 %), lo que deja poco margen: queda en la decisión del usuario si lo vale para un solo caso conocido; la reserva de hasta 50 % de la spec permitiría ampliar `QUERY_COMPLETE_FORWARD_NEIGHBORS` o `QUERY_COMPLETE_DOCUMENTS` si aparecen más listas cortadas en documentos grandes. `QUERY_RETRY_CUT_ANSWERS` no costó nada en la medición (no hubo cortes) y es una red de seguridad barata; mi recomendación es encenderla. No se encendió nada por defecto.

## Resultado de la feature 008 (pregunta limpia)

Medido el 2026-10-18 en producción con el código de `dev` y una medición reducida autorizada por el usuario: los 10 casos donde el segundo intento puede activarse (`S22-1`, `S22-3`, `S22-4`, `EN2`, `EN4`, `EN6`, `EN7`, `EN8`) o que prueban que no se activa (`EN9`, `EN10`), 26 consultas por corrida. Los demás casos (incluidos los 19 de la batería del MVP y `EN1`, `EN3`, `EN5`, `EN11`, `EN12`) no se midieron con respuestas porque su primera búsqueda ya pasa el umbral y ese camino es idéntico con la opción apagada o encendida. Dos corridas: `control8` (`QUERY_CLEAN_QUESTION=off`) y `limpia` (`on`), y la medición gratuita `limpia-previa` (puntajes). Gasto total de la feature: 0,021 USD. Detalle de los puntajes en `specs/008-pregunta-limpia/research.md` (R11).

| Qué | Resultado |
|---|---|
| Segundos intentos | 16 consultas lo tuvieron (8 casos por 2 modos). 12 encontraron fragmentos sobre el umbral y 4 no (`S22-3` y `EN4`, cuya forma corta puntúa 0,807). Los negativos `EN9` y `EN10` no lo tuvieron. |
| Casos que pasan de "sin información" a respuesta con el documento esperado | **2 consultas de 16**: `S22-1` y `EN2` (Natalia Soto Solís) en el modo con razonamiento. En literal no: su documento queda en el puesto 12 y el modo trae 8. |
| Segundo intento que encontró fragmentos pero el modelo respondió "sin información" | 10 consultas. `S22-4` y `EN6` (Cubillo): entraron 2 fragmentos de otro documento, el esperado puntúa 0,819, una milésima bajo el umbral. `EN7` y `EN8` (persona y término inventados): 8 fragmentos y el modelo respondió "sin información" en las 4 consultas. `S22-1` y `EN2` en literal: 8 fragmentos ajenos. |
| BUS-3 (respuestas inventadas) | **Se mantiene**: las 4 consultas con la persona y el término inventados terminaron en "sin información". |
| Costo | Las 10 llamadas al modelo que antes no se hacían costaron 0,008 USD en total (0,0001 a 0,0007 cada una, salvo `EN7` con razonamiento: 0,0046). Las 2 que dieron respuesta, 0,005 USD. Una consulta que antes era "sin información" gratis cuesta ahora cerca de 0,001 USD (hasta 0,005 con razonamiento) cuando el segundo intento encuentra fragmentos. |
| Latencia | Un segundo intento que no llega al modelo suma menos de 0,3 s (`S22-3`: 0,4 s a 0,7 s en literal). Con llamada al modelo la consulta tarda 1 a 3 s (una vez 7 s). |
| Opción apagada | `control8` contra `control7`: 2 diferencias, ambas en `S22-1` (corta, razonamiento) por las fuentes de la feature 006, que está encendida en Railway; ninguna atribuible a la 008. |
| Reglas | Un falso positivo hallado al listar las preguntas del conjunto de casos: `A2` ("¿Quién fue designado coordinador...?", voz pasiva) se reduciría a un fragmento de oración; se agregó una guarda. |

**Lectura.** La opción hace lo que el diseño prometía (no inventa, no llama al modelo en el segundo intento, no toca preguntas de dato, cuesta poco) pero **ayuda menos de lo esperado**: de tres personas, una (y solo con razonamiento). El límite es de recuperación y de umbral, no de envoltura: el documento de una persona aparece en los puestos 12 a 43 aun cuando se pregunta por el nombre solo, y el modo literal trae 8; en Cubillo el documento puntúa 0,819 frente a un umbral de 0,82. Las preguntas "háblame de..." ya pasan el umbral en la primera búsqueda con documentos ajenos, así que la opción no las toca. Quedan para el reranker (E) y la búsqueda híbrida (D). Una variante barata que no se probó: usar para el segundo intento un número de resultados mayor que el del modo (por ejemplo 16 en literal); trae más ruido al modelo y sube el costo, y requeriría su propia medición.

**Recomendación:** dejar `QUERY_CLEAN_QUESTION=off` en producción. Encenderla solo si se acepta un costo pequeño (cerca de 0,001 USD por consulta de identificación que hoy cae en "sin información") a cambio de acertar sobre todo en el modo con razonamiento; el valor real de esta etapa es sobre todo servir de base para el reranker, que comparte el mismo problema de qué recuperar.

## Resultado de la feature 009 (reranker local)

Medido el 2026-10-18 en tres pasos: puntajes del reranker contra Qdrant de producción en solo lectura (gratis, 57 casos y 28 variantes), memoria y latencia en la laptop de desarrollo (gratis) y una medición reducida en Railway con el código de `dev`, autorizada por el usuario (12 casos, ambos modos, control y dos corridas con reranker; tope 0,10 USD el control y 0,20 USD cada corrida con reranker; gasto real 0,014 USD el control y 0,005 y 0,006 USD las corridas con reranker). Modelo `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` (ONNX int8, 119 MB, Apache 2.0). Detalle en [research.md](../specs/009-reranker-local/research.md) (R13 y R14).

| Qué | Resultado |
|---|---|
| Casos que pasan de "sin información" a respuesta con el documento esperado | **5 de 5 personas con documento entre los 30 primeros candidatos**: `S22-1` (puesto 14 por coseno), `S22-4` (Cubillo, 19), `EN2` (25), `EN5` (17) y `EN6` (25), en los dos modos. Natalia Soto Solís y Cubillo responden con la pregunta completa, sin necesitar la pregunta limpia de la feature 008. |
| Casos que no mejoran | Joseph Obando (`S22-3`, `EN3`, `EN4`: su documento puntúa 0,000 en el reranker, el texto no parece hablar de él), `S22-2` (líneas de TFG, ausente entre los candidatos), las siglas (`SG3`, `LL2`: el documento no entra entre los candidatos), `EN1` (puesto 43) y `EN10`. Son límites de recuperación, no de reranking. |
| Regresión | `IN3` (pregunta indirecta sobre un acta): el reranker le da 0,009 a su documento y con el mínimo 0,06 responde "sin información" (antes respondía bien). Con cualquier mínimo que bloquee los casos sin respuesta se pierde. |
| BUS-3 (respuestas inventadas) | **Se mantiene**: con el mínimo 0,06 ninguno de los 14 casos sin respuesta pasa (personas y términos inventados, otro dominio, sigla inventada), y en Railway los 5 medidos terminaron en "sin información" sin llamar al modelo. **El margen es estrecho**: el mayor puntaje de un caso sin respuesta es 0,057 (`SR6`, "¿Qué es el PRGX?") contra el mínimo 0,06; el documento correcto más bajo que aún pasa es `IN1` con 0,069. Con el coseno, los mismos casos puntuaban entre 0,80 y 0,87. |
| Mínimo del reranker | Un mínimo "razonable" no sirve: con 0,5 el reranker rechaza 6 casos que hoy responden bien (`IN1`, `IN2`, `IN3`, `SG2`, `EN11`, `EN12`), preguntas de tema o de "qué es un curso" cuyos documentos no responden en forma de pasaje. Los valores por defecto (`RERANK_MIN_SCORE=0.06`) salen de esta calibración con los mismos 57 casos: riesgo de sobreajuste. |
| Latencia añadida (Railway) | **Cumple**: puntuar 20 o 30 candidatos con 128 tokens por pasaje y 4 hilos tarda 0,30 s en p50 y 0,34 s en p95 (28 puntuaciones por corrida; el número de candidatos casi no cambia el tiempo). Una consulta sin respuesta pasa de 0,4 s a 0,7 s de punta a punta. En la laptop de desarrollo el mismo cálculo tardó 0,82 s (20 candidatos) y 1,23 s (30), unas 2,7 veces más. |
| Memoria (Railway) | **No cumple por poco**: 366 MB sin el reranker y 522 a 524 MB con él en reposo (+158 MB), con picos de 593 a 610 MB. El límite era 512 MB. |
| Costo mensual | Estimado, sin medir: +158 MB de memoria son unos 1,6 USD al mes si el servicio está encendido todo el mes (10 USD por GB al mes), y la API pasaría de unos 4 a 4,5 USD a unos 5,6 a 6,1 USD, sobre los 5 USD incluidos del plan Hobby. La CPU del reranker (0,3 s por consulta) es despreciable con el tráfico actual. |
| Costo por consulta | El reranker no agrega llamadas al modelo de lenguaje. El gasto de las corridas medidas fue de 0,0065 y 0,0049 USD con reranker contra 0,0141 USD del control: centavos, sin una diferencia atribuible al reranker (cambian qué consultas llegan al modelo). |
| Piso de similitud | No ayuda: los 30 candidatos puntúan entre 0,78 y 0,91 en todos los casos. La variable `RERANK_MIN_SIMILARITY` se retiró (research R15). |
| Opción apagada | Cubierta por las pruebas automáticas (nada cambia con `RERANK_PROVIDER=none`); la corrida de control no registra notas del reranker. |

**Lectura.** El reranker resuelve lo que el coseno no podía: separa las preguntas sin respuesta (personas y términos inventados puntúan por debajo de 0,06, no 0,83) y rescata a las personas cuyos documentos estaban en los puestos 14 a 25, algo que ni la pregunta limpia (008) lograba. Corre en Railway dentro de la latencia fijada, sin servicio externo y sin llamadas nuevas al modelo de lenguaje. Lo que cuesta: unos 158 MB más de memoria (queda unos 10 MB sobre el límite de 512 MB) y, por estimación, 1 USD al mes más sobre el plan, y una regresión conocida (`IN3`). No resuelve Obando, TFG ni las siglas (lo cubre la búsqueda híbrida, opción D).

**Recomendación:** **conservar** el reranker apagado (`RERANK_PROVIDER=none`) y encenderlo cuando el usuario acepte explícitamente el exceso de memoria (unos 10 MB sobre el límite) y el costo estimado de 1 a 1,6 USD al mes. Antes de encenderlo en producción: agregar casos sin respuesta para afianzar el mínimo (el margen actual es de 0,003) y revisar si se puede recortar memoria. La búsqueda híbrida (D) sigue siendo necesaria para siglas y nombres cuyo documento no entra entre los candidatos.

## Resultado de la feature 010 (búsqueda híbrida)

Medido el 2026-10-19 en tres pasos, todos sin tokens de modelos de lenguaje: (1) calibración en un Qdrant local con una copia de los 6.239 fragmentos de producción (`scripts/copiar_coleccion.py`, origen en solo lectura), (2) la misma medición contra el Qdrant de producción en solo lectura, después de crear el índice de texto (autorizado por el usuario), y (3) latencia de la parte léxica contra los dos. 70 casos (los 57 anteriores y 13 nuevos, `HB1` a `HB7` y `HS1` a `HS6`) con 98 preguntas entre variantes. La medición con respuestas en Railway **no se hizo** (no autorizada): la migración `0005` y el despliegue de `dev` siguen pendientes. Diseño y calibración en [research.md](../specs/010-busqueda-hibrida/research.md) (R4, R5 y R16).

| Qué | Resultado |
|---|---|
| Documento esperado en la lista final | **Literal: 40 -> 65 de 69 casos. Razonamiento: 44 -> 65 de 69.** Mejoran las tres personas de la sección 2.2 (con pregunta completa y corta), `S22-2` (líneas de TFG con la forma desarrollada), `EN1` a `EN6` y sus variantes limpias, `EN10`, `HB1`, `HB2` (apellido repetido en cada página de una tesis) y `HB7` (código de curso). **Ninguno empeora.** |
| BUS-1 y BUS-2 (las 8 preguntas de la sección 2.2) | **Pasan de 1 a 8 en literal y de 2 a 8 con razonamiento.** Antes fallaban 7 y 6. |
| Casos "sin información" | **Ninguno empieza a llegar al modelo**: `N1`, `I1` a `I3`, `SR1` a `SR7`, `EN7` a `EN9`, `HS1` a `HS6` no reciben candidatos léxicos con el valor por defecto (incluso `I1`, que hoy ya llega al modelo, deja de recibirlos). La regla es la mayoría de las palabras específicas y una palabra ausente cuenta como específica. |
| Valor de `HYBRID_MAX_DOCS` | Barrido: con 3 documentos entran 29 objetivos y `HS4` recibe candidatos; con 5, 37; **con 10, 56 y ninguno sin información**; con 20, 58 pero `I1`; con 50, 57 con `I1` y `SR3`. Se fijó **10**. La primera versión contaba fragmentos (máximo 60) y dejaba fuera a `HB2`: un apellido repetido en 123 fragmentos de un solo documento es específico. |
| Ranuras para fragmentos solo por palabras | Con 0 el documento no entra (40); con 1 a 5, 65 y ningún caso sin información responde. Por defecto 3. |
| Casos que siguen sin resolverse (4 de 69) | `SG3` y `HB5` (MGTI): la sigla con su forma desarrollada aparece en 14 documentos del dominio de Currículum y deja de ser específica (con 20 documentos lo sería, pero entra `I1`). `LL2` (contenidos de Deep Learning): la parte léxica trae 25 candidatos pero el coseno pone primero fragmentos de otros programas; sigue siendo el caso de recuperación conocido. |
| Límites del texto extraído | `HB3` (Valeria Calderón) se responde solo por significado: en el texto de los PDF el acento queda aparte ("Calder´on") y `calderon` no coincide. `HS3` (persona inventada con dos de tres palabras reales) no recibe candidatos por esa misma razón: queda como caso para poner a prueba la regla cuando el texto lo permita. |
| Local frente a producción | **Idénticos** en las 98 mediciones (mismos candidatos y mismos resultados por modo): el índice de Qdrant Cloud 1.19.1 se comporta como el local. |
| Latencia de la parte léxica | Local (red de la misma máquina): hilo p50 9 ms y p95 16 ms; espera y fusión p50 5 ms y p95 10 ms. **Contra Qdrant Cloud desde la laptop del usuario** (unos 80 ms de ida y vuelta, más que desde Railway): hilo p50 122 ms, espera y fusión **p50 82 ms y p95 203 ms** (máximo 874 ms en una consulta), con la búsqueda por significado en p50 84 ms. Cumple el objetivo de SC-007 (0,2 s en p50 y 0,5 s en p95); la espera se solapa con la búsqueda por significado y con el reranker si estuviera encendido. |
| Memoria y almacenamiento | La API no suma RAM (no hay modelo ni índice en su proceso). En Qdrant: crear el índice tarda 1,5 s; el almacenamiento de la colección copiada queda en 52 MB; en el contenedor local `docker stats` pasa de unos 93 MB a unos 233 MB con el índice en disco (cifra que incluye la caché de archivos mapeados). Qdrant Cloud: sin medir. |
| Respuestas y costo | **No medidos** (sin autorización de gasto ni de despliegue). Por diseño la parte léxica no llama a ningún modelo; el costo adicional son las consultas que antes eran "sin información" y ahora tienen respuesta (cada una cuesta lo que cuesta una respuesta). |
| Opción apagada | Cubierta por pruebas automáticas: con `QUERY_HYBRID_SEARCH=off` (o un valor inválido) la ruta no llama a la parte léxica, no lee la tabla de siglas y entrega lo mismo que antes. |
| Vuelta atrás | Probada en SQLite el 2026-10-19: `prototipo-v2-estable` no arranca sobre la revisión `0005` y arranca sobre la devuelta con `alembic downgrade 0004` (borra solo `sigla_equivalences`); al volver a la versión nueva la base sube sola. El índice de texto no afecta a la API anterior. En Neon no se probó. |

**Lectura.** La búsqueda por palabras resuelve lo que ni la pregunta limpia ni el reranker lograban: los nombres propios y las siglas que la similitud de vectores no distingue, incluidos los apellidos repetidos en cada página de un documento y los nombres pegados a un carné ("Obando2023800202"). No sube el costo de los modelos, no necesita RAM en la API y se apaga con una variable. Lo que cambió respecto del diseño inicial es la medida de "palabra específica": por documentos distintos y no por fragmentos. Con 4 de 69 casos sin resolver por razones propias de los datos (una sigla presente en muchos documentos, un programa que el coseno no prioriza y acentos partidos en el texto extraído).

**Recomendación (SC-011): conservar y encender cuando el usuario decida.** Cumple lo medido en recuperación sin empeorar ningún caso ni hacer llegar al modelo ninguna pregunta sin respuesta, sin costo de RAM en la API ni de modelos, y es reversible. Antes de encender: aplicar la migración `0005` (el despliegue de `dev` la aplica sola al arrancar), crear el índice en producción (ya creado el 2026-10-19; se quita con `scripts/palabras.py quitar`) y medir con respuestas en Railway los casos que cambian y la batería del MVP, con tope de gasto. No hace falta combinarla con el reranker local ahora: el reranker queda apagado por la decisión del 2026-10-18 y los casos que le tocaban (personas con el documento en los puestos 14 a 25) los resuelve esta opción sin su costo de memoria.
