# Feature Specification: Eliminación de fuentes (documentos) de los dominios

**Feature Branch**: `dev` (feature `012-eliminar-documentos`, sin rama propia por decisión del usuario)

**Created**: 2026-10-26

**Status**: Draft

**Input**: User description: "Eliminación de fuentes (documentos) de los dominios. Hoy MIA permite subir documentos a un dominio desde el panel de administración (módulo Inventario) y por la API, pero no hay forma de quitarlos. Se quiere que una persona administradora pueda eliminar un documento de un dominio, con el mismo alcance que ya tiene para subirlo (global o por programa), desde el Inventario del panel y desde la API, y que la eliminación sea completa: el documento deja de aparecer en el inventario, sus fragmentos dejan de usarse en las respuestas, se quitan también sus imágenes asociadas (y sus enlaces públicos dejan de servir) y no quedan restos huérfanos. Debe pedir confirmación, dejar constancia en el registro de administración, funcionar con documentos en cualquier estado sin dejar la ingesta a medias, permitir volver a subir el mismo archivo, conservar el historial de Uso, permitir eliminar varios a la vez y dejar documentado cómo se recupera un documento eliminado por error. Fuera de alcance: eliminar dominios o programas completos, papelera con restauración y cambios al versionado de documentos."

Contexto: hoy un documento cargado en MIA no se puede quitar. Quien administra no puede borrar uno subido por error, uno desactualizado (por ejemplo, la información de un proceso de admisión que ya venció, como las fechas de la Maestría en Ciberseguridad cargadas para probar el bot de WhatsApp) ni uno que no debía quedar disponible. Mientras siga cargado, ese documento sigue alimentando las respuestas de **todos** los artefactos que ven su dominio: la Consulta administrativa y el bot de WhatsApp, que responde a personas externas. La única salida es tocar a mano la base de datos y el almacén de vectores, algo que solo puede hacer quien conoce el sistema por dentro y que puede dejar restos (fragmentos que siguen respondiendo, imágenes con su enlace público vivo, archivos). Tres hechos condicionan el diseño:

1. **Un documento deja huella en varios lugares.** Su registro en el inventario, sus fragmentos buscables (de donde salen las respuestas), sus imágenes asociadas con enlaces públicos, el archivo original que se guardó al subirlo y la huella que impide subir dos veces el mismo contenido. Eliminarlo es quitarlo de todos, o no es eliminarlo.
2. **Lo que importa es que deje de responderse con él.** Un documento que desaparece del inventario pero cuyos fragmentos siguen en el almacén de vectores sigue contestando preguntas y citándose como fuente: el peor resultado posible, porque la persona administradora cree que ya no está.
3. **El historial no se reescribe.** Las consultas pasadas que citaron el documento quedan en el registro de Uso tal como ocurrieron, con el nombre del documento que se citó entonces.

## Clarifications

### Session 2026-10-26

- Q: ¿Quién puede eliminar un documento? → A: Quien ya puede subirlo: una persona administradora con alcance global o con alcance sobre el programa del dominio. No se crea un permiso nuevo.
- Q: ¿Se puede deshacer? → A: No. No hay papelera ni restauración. Si un documento se elimina por error, se recupera volviendo a subir el archivo original, y esa forma de recuperarlo debe quedar documentada.
- Q: ¿Qué pasa con las consultas pasadas que citaron el documento? → A: Se conservan en el registro de Uso sin cambios.
- Q: ¿Se eliminan también dominios, programas o carpetas completos? → A: No. Esta feature es solo para documentos sueltos. Los dominios y programas completos y los cambios al versionado de documentos quedan fuera de alcance.
- Q: ¿Se pueden eliminar varios documentos a la vez? → A: Sí, es deseable (prioridad menor): elegir varios en el Inventario y eliminarlos con una sola confirmación.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Quien administra elimina un documento desde el Inventario y las respuestas dejan de usarlo (Priority: P1)

Una persona administradora abre el Inventario, encuentra el documento `Maestria_en_Ciberseguridad.txt` (cargado para probar y ya vencido) y elige eliminarlo. El panel le pide confirmar y le dice con claridad qué se va a perder y que no se puede deshacer. Al confirmar, el documento desaparece del inventario. A partir de la consulta siguiente, ninguna respuesta de ningún artefacto (la Consulta administrativa ni el bot de WhatsApp) se apoya en su contenido ni lo cita como fuente.

**Why this priority**: es el propósito de la feature. Sin esto, un documento equivocado o vencido sigue respondiendo y solo se puede quitar a mano.

**Independent Test**: cargar un documento de prueba con un dato que ninguna otra fuente tenga, comprobar que una pregunta por ese dato lo cita, eliminarlo desde el panel y repetir la pregunta: la respuesta es "sin información" y el documento no figura en ninguna fuente.

**Acceptance Scenarios**:

1. **Given** un documento listo en un dominio, **When** la persona administradora elige eliminarlo, **Then** el panel pide confirmación antes de hacer nada y la confirmación nombra el documento y dice que se pierden el documento, sus imágenes asociadas y su contenido en las respuestas, y que no se puede deshacer.
2. **Given** la confirmación abierta, **When** la persona cancela o cierra el diálogo, **Then** no se elimina nada.
3. **Given** la confirmación, **When** la persona confirma, **Then** el documento desaparece del inventario y el contador de documentos de su dominio, carpeta y programa baja en uno.
4. **Given** un documento eliminado, **When** cualquier artefacto hace una consulta cuya respuesta estaba solo en ese documento, **Then** responde "sin información suficiente" y el documento no aparece entre las fuentes.
5. **Given** un documento eliminado, **When** un artefacto consulta algo que está también en otros documentos, **Then** responde con los demás documentos, que no se ven afectados.
6. **Given** un documento de una carpeta que solo tenía ese documento, **When** se elimina, **Then** la carpeta queda vacía y se puede borrar con la acción de siempre (hoy una carpeta con documentos no se puede borrar).

---

### User Story 2 - La eliminación es completa y no deja nada a medias (Priority: P1)

Eliminar un documento quita todo lo que dejó: su registro, sus fragmentos buscables, sus imágenes asociadas (y sus enlaces públicos dejan de servir) y el archivo original que se guardó al subirlo. Si algo falla en el camino, el documento no queda "medio eliminado": o se elimina por completo o sigue como estaba, con un aviso claro, y reintentar es seguro.

**Why this priority**: un documento que desaparece del inventario pero cuyos fragmentos siguen respondiendo es peor que no poder eliminarlo, porque la persona administradora cree que ya no está. Es la garantía que hace útil a la feature.

**Independent Test**: eliminar un documento con imágenes asociadas y comprobar que ni sus fragmentos ni sus imágenes ni su archivo ni su registro quedan; simular una falla a mitad de la eliminación y comprobar que el documento sigue visible y que reintentar lo termina.

**Acceptance Scenarios**:

1. **Given** un documento con imágenes asociadas, **When** se elimina, **Then** sus enlaces públicos dejan de servir (responden "no encontrada") y las imágenes ya no figuran en ninguna parte.
2. **Given** un documento eliminado, **When** se revisan los fragmentos del almacén de búsqueda, **Then** no queda ninguno de ese documento.
3. **Given** un documento eliminado, **When** se revisan los archivos originales guardados, **Then** el de ese documento ya no está (si no existía, la eliminación no falla por eso).
4. **Given** una falla al quitar sus fragmentos del almacén de búsqueda, **When** se intenta eliminar, **Then** el documento sigue en el inventario, la persona recibe un aviso de que no se pudo eliminar y puede reintentar, sin que nada haya quedado a medias.
5. **Given** una eliminación que falló antes de terminar, **When** se reintenta, **Then** termina bien aunque ya se hubiera quitado una parte (por ejemplo, ya no estén los fragmentos).
6. **Given** que se pide eliminar un documento que ya no existe (por ejemplo, dos personas lo eliminan a la vez), **When** llega la segunda petición, **Then** responde que no existe, sin error confuso y sin afectar a otros documentos.

---

### User Story 3 - El alcance se respeta y cada eliminación queda registrada (Priority: P1)

Una persona administradora solo puede eliminar documentos de los dominios sobre los que ya tiene alcance (todos si es global, los de sus programas si es de programa), igual que para subirlos. Cada eliminación deja constancia en el registro de administración: quién, qué documento (su nombre y su identificador), de qué dominio y cuándo.

**Why this priority**: eliminar es una acción destructiva sobre información que otros artefactos usan. Sin alcance y sin constancia, un error o un abuso no se puede acotar ni explicar.

**Independent Test**: con una cuenta de alcance de programa, eliminar un documento propio (funciona) y uno de otro programa (se rechaza y queda anotado el rechazo), y comprobar las líneas del registro de administración en cada caso.

**Acceptance Scenarios**:

1. **Given** una persona con alcance sobre el programa de un dominio, **When** elimina un documento de ese dominio, **Then** se elimina.
2. **Given** una persona con alcance sobre un solo programa, **When** intenta eliminar un documento de un dominio de otro programa, **Then** se rechaza con el mismo mensaje de "fuera de tus programas" que ya usa el panel, el documento sigue intacto y el rechazo queda en el registro de administración.
3. **Given** una persona con alcance global, **When** elimina un documento de cualquier dominio, incluso uno sin programa, **Then** se elimina.
4. **Given** una eliminación hecha, **When** se revisa el registro de administración, **Then** hay una línea con quién la hizo (correo o la clave de automatización), qué documento (nombre e identificador), de qué dominio y cuándo, sin ningún contenido del documento.
5. **Given** quien no ha iniciado sesión o no está autorizado, **When** intenta eliminar, **Then** se rechaza sin tocar nada.
6. **Given** la clave de un artefacto (de las que consultan), **When** intenta eliminar un documento, **Then** se rechaza: los artefactos solo consultan.

---

### User Story 4 - Se pueden eliminar documentos en cualquier estado (Priority: P2)

Un documento puede estar en cola, procesándose, listo o con error. En cualquiera de esos estados se puede eliminar sin dejar la ingesta a medias: un documento que se elimina mientras todavía se está procesando no debe reaparecer ni dejar fragmentos cuando termine de procesarse.

**Why this priority**: lo más común es eliminar documentos listos, pero un documento con error o uno subido por equivocación que aún está en cola también se debe poder quitar. El caso de "se elimina mientras se procesa" es el que más fácil deja restos si no se cuida.

**Independent Test**: subir un documento grande, eliminarlo mientras se procesa, esperar a que la ingesta termine y comprobar que no existe ni su registro ni ningún fragmento suyo; eliminar uno con error y uno en cola.

**Acceptance Scenarios**:

1. **Given** un documento con error de procesamiento, **When** se elimina, **Then** se elimina (es lo que más se necesita para limpiar un intento fallido).
2. **Given** un documento en cola que todavía no empezó a procesarse, **When** se elimina, **Then** nunca llega a procesarse ni deja fragmentos.
3. **Given** un documento que se está procesando, **When** se elimina, **Then** al terminar la eliminación no queda ningún fragmento suyo, y el procesamiento no lo vuelve a crear después.
4. **Given** varios documentos en cola y uno de ellos eliminado, **When** la ingesta sigue, **Then** procesa normalmente los demás.

---

### User Story 5 - Eliminar desde la API, para scripts y automatizaciones (Priority: P2)

Quien opera el sistema con scripts (por ejemplo la carga masiva de carpetas) puede eliminar un documento por la API de administración, con la misma garantía, el mismo alcance y el mismo registro que desde el panel. Así se pueden limpiar documentos de prueba o reemplazar los de un dominio sin entrar al panel.

**Why this priority**: es parte de lo pedido ("desde el Inventario del panel y desde la API"), y el panel y los scripts deben tener la misma regla. Es de prioridad menor porque el panel cubre el uso diario.

**Independent Test**: eliminar un documento con la clave de automatización, verificar el resultado y el registro, y comprobar que repetir la petición responde que no existe.

**Acceptance Scenarios**:

1. **Given** la clave de automatización, **When** se pide eliminar un documento de un dominio, **Then** se elimina con todas las garantías de las historias 1 y 2 y responde sin contenido (éxito).
2. **Given** un documento que no existe, o que no pertenece al dominio indicado, **When** se pide eliminarlo, **Then** responde que no se encontró y no toca nada.
3. **Given** una cuenta de programa, **When** pide eliminar con la API un documento fuera de su alcance, **Then** se rechaza igual que en el panel.

---

### User Story 6 - Volver a subir el mismo archivo tras eliminarlo (Priority: P2)

Después de eliminar un documento, se puede volver a subir el mismo archivo al mismo dominio. El sistema no debe seguir tratándolo como un duplicado del que ya no existe. Es también la forma de recuperar un documento eliminado por error: subir de nuevo el archivo original. Esa forma de recuperarlo queda documentada.

**Why this priority**: sin esto, eliminar para volver a cargar una versión corregida del mismo archivo quedaría bloqueado por la detección de duplicados. Y es la única "red de seguridad" ante un error, ya que no hay papelera.

**Independent Test**: eliminar un documento y volver a subir exactamente el mismo archivo al mismo dominio: se acepta como documento nuevo y responde consultas de nuevo.

**Acceptance Scenarios**:

1. **Given** un documento eliminado, **When** se sube el mismo archivo al mismo dominio, **Then** se acepta como un documento nuevo (no responde "ya existía") y, una vez procesado, vuelve a responder consultas.
2. **Given** un documento eliminado, **When** se sube un archivo con el mismo contenido a otro dominio, **Then** se acepta igual que antes.
3. **Given** un documento eliminado por error, **When** la persona consulta la documentación de operación, **Then** encuentra cómo recuperarlo (volver a subir el archivo original) y qué no se recupera (sus imágenes asociadas, que hay que asociar de nuevo).

---

### User Story 7 - Eliminar varios documentos a la vez (Priority: P3)

La persona administradora elige varios documentos del Inventario y los elimina con una sola confirmación, que lista cuáles son. Si alguno no se puede eliminar, los demás sí se eliminan y se le dice cuáles fallaron y por qué.

**Why this priority**: es una comodidad ("conviene"), útil al limpiar documentos de prueba o de un proceso vencido, pero la feature funciona sin ella.

**Independent Test**: elegir tres documentos, confirmar una sola vez y comprobar que los tres desaparecen; repetir con uno que falle y comprobar que los otros dos sí se eliminaron y que el aviso nombra el que falló.

**Acceptance Scenarios**:

1. **Given** varios documentos elegidos, **When** la persona elige eliminarlos, **Then** una única confirmación lista sus nombres y advierte lo que se pierde.
2. **Given** la confirmación, **When** se confirma, **Then** todos se eliminan con las mismas garantías que uno solo.
3. **Given** que alguno no se puede eliminar, **When** termina la operación, **Then** los demás quedaron eliminados y el resultado nombra los que fallaron y el motivo de cada uno, sin dejar ninguno a medias.
4. **Given** una selección que incluye documentos de varios dominios, **When** se elimina, **Then** cada uno se valida con su propio alcance y los fuera de alcance se rechazan sin afectar a los demás.

---

### User Story 8 - Lo demás no cambia (Priority: P1)

Eliminar un documento no afecta a los otros documentos, ni a los artefactos, ni al historial. Las consultas pasadas que lo citaron siguen en el registro de Uso con el nombre que tenía; los artefactos, sus accesos y sus topes quedan igual; y los demás documentos del dominio siguen respondiendo.

**Why this priority**: es una operación destructiva sobre una API compartida por todos los artefactos. No debe romper nada fuera del documento.

**Independent Test**: eliminar un documento y comprobar que el resto del inventario, los artefactos, los topes y el historial de consultas están igual, y que las pruebas existentes siguen pasando.

**Acceptance Scenarios**:

1. **Given** consultas pasadas que citaron un documento, **When** se elimina, **Then** siguen en el registro de Uso (listado, detalle y descarga) sin cambios, con el nombre del documento citado entonces.
2. **Given** otros documentos del mismo dominio, **When** se elimina uno, **Then** los demás siguen listos y respondiendo.
3. **Given** los artefactos existentes, **When** se elimina un documento, **Then** sus claves, accesos, modos y topes no cambian.
4. **Given** la batería de aceptación del MVP y las pruebas existentes, **When** se ejecutan tras esta feature, **Then** dan el mismo resultado que antes.

---

### Edge Cases

- El documento que se elimina es el único de un dominio: el dominio queda vacío y sigue existiendo (los dominios no se eliminan).
- El documento tiene imágenes asociadas: se eliminan con él y sus enlaces dejan de servir. Si se vuelve a subir el archivo, las imágenes hay que asociarlas de nuevo (un documento nuevo no hereda las del anterior).
- Se elimina un documento mientras una persona hace una consulta que lo usa: la consulta en curso termina con lo que ya había recuperado y la siguiente ya no lo usa.
- Se elimina un documento mientras se procesa (en cola o a mitad de procesarse): no debe reaparecer ni dejar fragmentos cuando la ingesta termine.
- Dos personas eliminan el mismo documento a la vez: una lo elimina y la otra recibe que ya no existe.
- La eliminación falla a la mitad (por ejemplo, el almacén de búsqueda no responde): el documento no queda "medio eliminado"; sigue visible y la persona puede reintentar.
- El archivo original ya no existe en el servidor (los servicios de despliegue no conservan los archivos subidos): eliminar no falla por eso.
- Un documento viejo sin imágenes, sin archivo guardado y con fragmentos antiguos: se elimina igual.
- Se elimina un documento citado por una respuesta que otra persona tiene en pantalla: la respuesta ya entregada no cambia (no se puede retirar); solo las consultas nuevas dejan de usarlo.
- El registro de Uso conserva el nombre del documento citado, aunque ya no exista en el inventario: no es un error ni se intenta "arreglar".
- Se elimina un documento con un nombre repetido en otro dominio u otro programa: solo se elimina el que se eligió.
- La selección múltiple incluye un documento que otra persona ya eliminó: se informa que ya no existe y se sigue con los demás.

## Requirements *(mandatory)*

### Functional Requirements

**Eliminar un documento**

- **FR-001**: Una persona administradora debe poder eliminar un documento de un dominio desde el Inventario del panel de administración.
- **FR-002**: Una persona administradora o un script con la clave de automatización debe poder eliminar un documento de un dominio por la API de administración, con el mismo resultado, el mismo alcance y el mismo registro que desde el panel.
- **FR-003**: Antes de eliminar desde el panel, se debe pedir confirmación que nombre el documento y diga qué se pierde (el documento, sus imágenes asociadas y su contenido en las respuestas) y que la acción no se puede deshacer. Cancelar o cerrar la confirmación no elimina nada.
- **FR-004**: Al eliminar, el documento debe desaparecer del inventario, y los contadores de documentos de su dominio, carpeta y programa deben reflejarlo de inmediato.
- **FR-005**: Pedir eliminar un documento que no existe, o que no pertenece al dominio indicado, debe responder que no se encontró, sin afectar a ningún otro documento.

**Eliminación completa**

- **FR-006**: Desde la consulta siguiente a una eliminación, ninguna consulta de ningún artefacto debe responder con el contenido del documento eliminado ni citarlo como fuente.
- **FR-007**: Eliminar un documento debe quitar sus fragmentos del almacén de búsqueda, de modo que no quede ninguno suyo.
- **FR-008**: Eliminar un documento debe quitar sus imágenes asociadas, y los enlaces públicos de esas imágenes deben dejar de servir (responder "no encontrada").
- **FR-009**: Eliminar un documento debe quitar el archivo original guardado al subirlo, si existe. Que no exista no debe impedir la eliminación.
- **FR-010**: Eliminar un documento debe quitar su registro del inventario y la huella con que se detectan los duplicados, de modo que no queden restos sin dueño en ningún almacén (registros de documentos, imágenes, fragmentos ni archivos).
- **FR-011**: La eliminación no debe dejar un documento "a medias". Si no se puede completar, el documento debe seguir visible en el inventario, la persona debe recibir un aviso claro de que no se pudo eliminar y reintentar debe ser seguro: completa lo que falte aunque ya se hubiera quitado una parte.
- **FR-012**: El orden de la eliminación no debe permitir que el documento deje de verse en el inventario mientras sus fragmentos siguen respondiendo consultas.

**Estados del documento**

- **FR-013**: Se debe poder eliminar un documento en cualquier estado: en cola, procesándose, listo o con error.
- **FR-014**: Eliminar un documento que todavía no se procesó debe impedir que se procese después. Eliminar uno que se está procesando no debe dejar fragmentos ni permitir que el procesamiento lo vuelva a crear al terminar.
- **FR-015**: Eliminar un documento no debe detener ni afectar la ingesta de los demás documentos en cola.

**Alcance, seguridad y registro**

- **FR-016**: Solo puede eliminar un documento quien ya puede subirlo a su dominio: una persona con alcance global o con alcance sobre el programa del dominio, o la clave de automatización. No se crea un permiso nuevo.
- **FR-017**: Un intento de eliminar fuera del alcance debe rechazarse con el mensaje de alcance que ya usa el panel, sin tocar nada, y dejar el rechazo en el registro de administración.
- **FR-018**: Cada eliminación hecha debe dejar una línea en el registro de administración con quién la hizo, el nombre y el identificador del documento, su dominio y cuándo, sin ningún contenido del documento.
- **FR-019**: Las claves de los artefactos que consultan no deben poder eliminar documentos.

**Volver a subir y recuperación**

- **FR-020**: Tras eliminar un documento se debe poder volver a subir el mismo archivo al mismo dominio, que se acepta como documento nuevo y no como un duplicado del eliminado.
- **FR-021**: La documentación de operación debe explicar cómo recuperar un documento eliminado por error (volver a subir el archivo original) y que sus imágenes asociadas no se recuperan, hay que asociarlas de nuevo.

**Selección múltiple**

- **FR-022**: Se deben poder elegir varios documentos del Inventario y eliminarlos con una sola confirmación que liste sus nombres y advierta lo que se pierde.
- **FR-023**: En una eliminación múltiple cada documento se valida y se elimina por separado, con las mismas garantías: si alguno falla o está fuera de alcance, los demás se eliminan y el resultado nombra los que fallaron y el motivo, sin dejar ninguno a medias.

**Lo que no cambia**

- **FR-024**: Las consultas pasadas que citaron un documento eliminado deben conservarse en el registro de Uso sin cambios (listado, detalle y descarga), con el nombre del documento citado entonces.
- **FR-025**: Eliminar un documento no debe cambiar los otros documentos, los artefactos (claves, accesos, modos y topes), los dominios ni los programas.
- **FR-026**: Las pruebas existentes y la batería de aceptación del MVP deben seguir dando el mismo resultado.

**Documentación**

- **FR-027**: Al implementarse, la documentación de arquitectura y de operación debe quedar al día: cómo se elimina un documento (panel y API), qué se quita, cómo se recupera uno eliminado por error y que el registro de Uso conserva el historial.

### Key Entities *(include if feature involves data)*

- **Documento**: ya existe. Pertenece a un dominio y, opcionalmente, a una carpeta; tiene un estado (en cola, procesando, listo o con error) y una huella de contenido para detectar duplicados. Gana la posibilidad de eliminarse por completo.
- **Fragmentos del documento**: los trozos de texto buscables que salen de procesarlo y de donde se arman las respuestas. Se eliminan con el documento y son lo que más importa que no quede.
- **Imagen asociada a un documento**: ya existe (feature 011), con un enlace público. Se elimina con el documento y su enlace deja de servir.
- **Archivo original**: el archivo que se subió y se guarda para procesarlo. Se elimina con el documento si existe.
- **Registro de administración**: ya existe. Gana una línea por cada eliminación (y por cada rechazo) con quién, qué y cuándo.
- **Registro de consultas (Uso)**: ya existe. Guarda el nombre de los documentos citados por cada consulta; no se modifica al eliminar un documento.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Después de eliminar un documento, el 100 % de las preguntas cuya respuesta estaba solo en él responden "sin información suficiente", y el 0 % de las respuestas posteriores lo cita como fuente, en todos los artefactos (Consulta administrativa y bot de WhatsApp incluidos).
- **SC-002**: Tras eliminar un documento no queda ningún resto suyo: 0 fragmentos, 0 imágenes, 0 enlaces públicos que sirvan y 0 archivos guardados, comprobado en las pruebas con documentos que tenían imágenes y archivo.
- **SC-003**: Una persona administradora elimina un documento desde el Inventario, desde que lo elige hasta que desaparece de la lista, en menos de 30 segundos.
- **SC-004**: La eliminación de un documento típico (hasta 200 páginas, con imágenes) termina en menos de 10 segundos desde que se confirma.
- **SC-005**: En el 100 % de las eliminaciones hechas queda una línea en el registro de administración con quién, qué documento y cuándo, y en el 100 % de los intentos fuera de alcance queda anotado el rechazo y el documento sigue intacto.
- **SC-006**: En el 100 % de las pruebas con una falla simulada a la mitad de la eliminación, el documento no queda medio eliminado: sigue visible y reintentar lo termina; y en las de "eliminar mientras se procesa", no reaparece ni deja fragmentos.
- **SC-007**: Tras eliminar un documento, volver a subir el mismo archivo se acepta y vuelve a responder consultas en el 100 % de los casos.
- **SC-008**: Tras eliminar un documento, los demás documentos, los artefactos (claves, accesos, topes) y el historial de consultas están intactos: 0 diferencias en el registro de Uso y en el inventario salvo el documento eliminado.
- **SC-009**: La eliminación de varios documentos con una sola confirmación elimina el 100 % de los que se pueden eliminar aunque alguno falle, y el resultado nombra los que fallaron.
- **SC-010**: La batería del MVP da 19 de 19 como antes y todas las pruebas existentes siguen pasando.

## Assumptions

- Quien opera MIA es una sola persona (el usuario) y las personas administradoras tienen cuenta del TEC o usan la clave de automatización; el alcance (global o por programa) y el registro de administración existentes se reutilizan sin cambios de fondo.
- Eliminar es **definitivo**: no hay papelera ni restauración (fuera de alcance por decisión del usuario). La red de seguridad es volver a subir el archivo original, que la persona administradora debe conservar fuera de MIA (los servicios de despliegue no conservan los archivos subidos).
- Las imágenes asociadas a un documento no se recuperan al volver a subir el archivo: un documento nuevo no hereda las imágenes del eliminado (limitación ya conocida de la feature 011), y hay que asociarlas de nuevo.
- La confirmación es una responsabilidad de la interfaz (el panel); la API de administración elimina cuando se le pide de forma explícita, porque la usan scripts y no hay una persona que confirme en cada llamada.
- Los fragmentos viven en un almacén de búsqueda separado del registro de documentos. Que la eliminación sea completa y segura ante fallas (FR-011 y FR-012) es un requisito de comportamiento: cómo se ordenan los pasos y cómo se reintenta se decide en el plan.
- Un documento que se procesa en segundo plano puede tardar en terminar (la ingesta procesa uno a la vez); cómo se evita que reaparezca al eliminarlo a mitad de proceso se decide en el plan, pero el resultado debe cumplir FR-014.
- El registro de Uso guarda de cada consulta el nombre de los documentos que citó, no una referencia al documento; por eso conserva el historial sin cambios al eliminarlo y no hay nada que migrar.
- La detección de duplicados compara el contenido dentro de un dominio: al eliminar el documento desaparece esa huella, y volver a subirlo es un documento nuevo.
- Los documentos que hoy están cargados (incluidos los de prueba del bot de WhatsApp: `Maestria_en_Ciberseguridad.txt` y `Maestria_en_Ciberseguridad_enfasis.txt`) son los primeros candidatos a eliminar con esta feature; borrarlos no forma parte de ella.
- Quedan fuera de esta feature: eliminar dominios, programas o carpetas completos (la carpeta con documentos sigue sin poder borrarse hasta que se vacíe), una papelera con restauración, el versionado de documentos y cualquier cambio a cómo se procesan o se buscan.
- La eliminación no se anuncia a los artefactos ni a quienes ya recibieron una respuesta: lo ya entregado no se retira.
- Es un prototipo de vigencia corta: se prefiere lo más simple que cumpla la especificación (por ejemplo, eliminar de uno en uno primero y la selección múltiple como comodidad posterior).
