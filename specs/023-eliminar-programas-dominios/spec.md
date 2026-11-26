# Feature Specification: Eliminación de programas y dominios

**Feature Branch**: `dev` (feature `023-eliminar-programas-dominios`, sin rama propia)

**Created**: 2026-11-25

**Status**: Draft

**Input**: User description: "Eliminar programas y dominios desde el panel y la API. Hoy se pueden eliminar documentos (feature 012) y carpetas, pero no dominios ni programas: un programa o dominio creado por error queda para siempre. Quienes usarán el sistema desde ahora son personas sin conocimiento técnico, que no pueden correr scripts ni borrar filas en la base de datos."

Contexto: desde el panel se pueden crear programas, dominios y carpetas, pero solo las carpetas vacías y los documentos se pueden quitar. Un programa o dominio creado con un nombre equivocado, duplicado o de prueba se queda en el Inventario, en las listas al subir documentos y en la configuración de los artefactos. La única salida es tocar la base de datos, algo que las personas que administran MIA desde ahora no pueden hacer. La feature 012 dejó esto fuera de alcance a propósito.

Un programa o un dominio no está solo: un dominio contiene carpetas y documentos, y puede estar entre lo que un artefacto consulta; un programa contiene dominios, y además puede tener artefactos con acceso a él, cuentas de administración limitadas a él y usuarios de la Consulta asignados. El historial de Uso guarda consultas hechas sobre esos dominios.

## Clarifications

### Session 2026-11-25

- Q: ¿Qué pasa si el dominio o programa tiene contenido? → A: Solo se elimina si está vacío: un dominio sin documentos ni carpetas, un programa sin dominios. No hay eliminación en cascada.
- Q: ¿Y si un programa tiene usuarios de la Consulta, cuentas de administración o artefactos asociados? → A: Se rechaza hasta reasignarlos o quitarlos. Nadie pierde su asociación sin que alguien lo decida. En un dominio, en cambio, los artefactos con acceso a él simplemente dejan de verlo, con advertencia previa.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Quitar un dominio creado por error (Priority: P1)

Una persona administradora abre el Inventario, elige un dominio creado por error y lo elimina. El panel le pide confirmar, nombra el dominio y le dice qué se verá afectado. Al confirmar, el dominio desaparece del Inventario, de las listas para subir documentos y de la configuración de los artefactos.

**Why this priority**: es el caso más frecuente al organizar la memoria y hoy no tiene salida.

**Independent Test**: crear un dominio de prueba, eliminarlo desde el panel y comprobar que no aparece en el Inventario, al subir documentos ni al editar un artefacto, y que se puede crear otro con el mismo nombre.

**Acceptance Scenarios**:

1. **Given** un dominio sin documentos ni carpetas, **When** la persona elige eliminarlo, **Then** el panel pide confirmación nombrándolo antes de hacer nada.
2. **Given** la confirmación abierta, **When** cancela o la cierra, **Then** no se elimina nada.
3. **Given** la confirmación, **When** confirma, **Then** el dominio desaparece y se puede crear otro con el mismo nombre en el mismo programa.
4. **Given** un dominio con documentos o carpetas, **When** la persona intenta eliminarlo, **Then** se rechaza, no se borra nada y se le dice cuántos documentos y carpetas tiene que quitar primero.
5. **Given** un dominio vacío al que un artefacto tiene acceso puntual, **When** se elimina, **Then** la confirmación nombra el artefacto y, tras confirmar, este deja de tener ese acceso.

---

### User Story 2 - Quitar un programa creado por error (Priority: P1)

Una persona con alcance global elimina un programa que no debía existir. Desaparece del Inventario y de todas las listas donde se elige un programa.

**Why this priority**: un programa sobrante aparece en cada lista de selección y confunde a quien no conoce el sistema.

**Independent Test**: crear un programa de prueba, eliminarlo y comprobar que no aparece en ninguna lista y que se puede crear otro con el mismo nombre.

**Acceptance Scenarios**:

1. **Given** un programa sin dominios y sin nada asociado, **When** una persona con alcance global lo elimina y confirma, **Then** desaparece de todas las listas.
2. **Given** una persona con alcance de programa, **When** intenta eliminar un programa, **Then** se rechaza, igual que hoy se rechaza crearlo, y el rechazo queda registrado.
3. **Given** un programa con dominios, **When** se intenta eliminar, **Then** se rechaza y se nombran los dominios que hay que eliminar primero.
4. **Given** un programa con usuarios de la Consulta, cuentas de administración o artefactos con acceso a él, **When** se intenta eliminar, **Then** se rechaza y se nombra cada uno; ninguno cambia.

---

### User Story 3 - Reasignar a las personas de un programa (Priority: P1)

Quien administra cambia el programa de un usuario de la Consulta, o lo deja sin programa, desde el panel. Hoy el programa se elige al crear el usuario y no se puede cambiar.

**Why this priority**: sin esto, un programa con un solo usuario asignado no se podría eliminar nunca.

**Independent Test**: cambiar el programa de un usuario, comprobar que conserva su contraseña y su historial, y que el programa anterior ya se puede eliminar.

**Acceptance Scenarios**:

1. **Given** un usuario asignado a un programa, **When** una persona con alcance global lo mueve a otro o lo deja sin programa, **Then** el cambio queda hecho sin alterar su contraseña, sus conversaciones ni su estado.
2. **Given** una persona con alcance de programa, **When** intenta mover un usuario desde o hacia un programa fuera de su alcance, o dejarlo sin programa, **Then** se rechaza.

---

### User Story 4 - Entender por qué no se puede y qué hacer (Priority: P2)

Cuando una eliminación no se permite, el panel dice en lenguaje corriente qué la impide y qué hacer, con nombres y cantidades.

**Why this priority**: las personas que administran no tienen conocimiento técnico ni a quién preguntar en el momento.

**Independent Test**: intentar eliminar un programa o dominio que no cumple las condiciones y comprobar que el mensaje permite resolverlo sin ayuda.

**Acceptance Scenarios**:

1. **Given** algo que impide la eliminación, **When** la persona la intenta, **Then** ve la lista de lo que la impide (cuántos documentos, qué artefactos, qué personas) y el paso para resolver cada cosa.
2. **Given** lo que la impedía ya resuelto, **When** reintenta, **Then** la eliminación se completa.

---

### User Story 5 - El historial y lo demás no cambian (Priority: P1)

Eliminar un programa o dominio no altera otros programas, dominios ni documentos, y las consultas pasadas siguen en el registro de Uso de forma legible.

**Why this priority**: es una acción destructiva sobre información que comparten todos los artefactos.

**Independent Test**: eliminar un dominio sobre el que hubo consultas y comprobar que el registro de Uso se lee igual y que los demás dominios responden como antes.

**Acceptance Scenarios**:

1. **Given** consultas pasadas sobre un dominio, **When** se elimina, **Then** el registro de Uso (listado, detalle y descarga) las conserva y sigue diciendo de qué dominio eran.
2. **Given** un artefacto con acceso a varios dominios, **When** se elimina uno, **Then** sigue consultando los demás con la misma clave, modos y topes.
3. **Given** una eliminación hecha, **When** se revisa el registro de administración, **Then** consta quién, qué (nombre e identificador) y cuándo.

---

### Edge Cases

- El programa es el único acceso de un artefacto: como un artefacto no puede quedar sin ningún acceso, el mensaje indica darle otro acceso o eliminar el artefacto.
- Un usuario de la Consulta desactivado sigue asignado al programa: también impide eliminarlo y también se puede reasignar.
- Una cuenta de administración limitada al programa lo impide y, como esas cuentas no se gestionan desde el panel, el mensaje dice que hay que pedirlo a soporte técnico.
- El dominio eliminado era lo único que un artefacto podía consultar: el artefacto sigue existiendo y responde que no tiene información; el panel lo advierte antes de confirmar.
- Un bot de WhatsApp usa ese artefacto: la advertencia lo menciona, porque responde a personas externas.
- Alguien sube un documento al dominio mientras otra persona lo elimina: no pueden quedar documentos ni contenido buscable sin dominio.
- Dos personas eliminan lo mismo a la vez: una lo logra y la otra recibe que ya no existe.
- Se elimina el último programa: el Inventario queda vacío y permite crear uno nuevo.
- Un dominio sin programa (datos antiguos): solo lo puede eliminar quien tiene alcance global.
- La eliminación falla a la mitad: no queda nada "medio eliminado" y reintentar es seguro.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Una persona administradora MUST poder eliminar un dominio desde el Inventario del panel y por la API de administración, con el mismo resultado.
- **FR-002**: Eliminar un dominio MUST estar permitido a quien hoy puede crearlo: alcance global o alcance sobre su programa.
- **FR-003**: Eliminar un programa MUST estar permitido solo a quien tiene alcance global.
- **FR-004**: Las claves de artefacto MUST NOT poder eliminar programas ni dominios.
- **FR-005**: Un dominio MUST poder eliminarse solo si no tiene documentos ni carpetas; un programa, solo si no tiene dominios, usuarios de la Consulta, cuentas de administración ni artefactos con acceso a él. No hay eliminación en cascada de contenido.
- **FR-006**: Al eliminar un dominio, los accesos puntuales de los artefactos a él MUST quitarse junto con él.
- **FR-007**: Quien administra MUST poder cambiar o quitar el programa de un usuario de la Consulta desde el panel y la API, dentro de su alcance, sin alterar su contraseña, historial ni estado.
- **FR-008**: El panel MUST pedir una confirmación que nombre lo que se elimina, diga qué se verá afectado y que no se puede deshacer.
- **FR-009**: Cuando no se permita eliminar, el sistema MUST explicar qué lo impide y cómo resolverlo, sin términos técnicos.
- **FR-010**: Tras una eliminación, el programa o dominio MUST NOT aparecer en ninguna lista, configuración ni respuesta, y su nombre MUST quedar disponible de nuevo.
- **FR-011**: Una eliminación MUST NOT dejar carpetas, documentos, contenido buscable, imágenes ni accesos que apunten a algo que ya no existe.
- **FR-012**: Una eliminación MUST completarse entera o no cambiar nada, y reintentarla MUST ser seguro.
- **FR-013**: El registro de Uso MUST conservar las consultas pasadas y seguir identificando el dominio que tenían.
- **FR-014**: Cada eliminación y cada rechazo por alcance MUST quedar en el registro de administración.
- **FR-015**: Eliminar MUST NOT cambiar claves, modos ni topes de los artefactos, ni afectar otros programas o dominios.

### Key Entities

- **Programa**: agrupa dominios. Puede tener artefactos con acceso, cuentas de administración limitadas a él y usuarios de la Consulta asignados.
- **Dominio**: pertenece a un programa; contiene carpetas y documentos; los artefactos pueden consultarlo.
- **Artefacto**: consulta programas completos o dominios sueltos; los bots usan un artefacto.
- **Consulta registrada**: historial de Uso, con los dominios sobre los que se hizo.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Una persona sin conocimiento técnico elimina un dominio o programa creado por error en menos de 1 minuto y sin ayuda.
- **SC-002**: Después de eliminar, el 100 % de las listas y configuraciones dejan de mostrarlo y ninguna respuesta usa contenido que estuviera en él.
- **SC-003**: Quedan 0 elementos huérfanos tras cualquier eliminación, incluidas las que fallan a la mitad.
- **SC-004**: El 100 % de las consultas pasadas siguen siendo legibles en el registro de Uso.
- **SC-005**: Ningún caso de programa o dominio mal creado requiere ya acceso a la base de datos.

## Assumptions

- Las cuentas de administración se siguen gestionando fuera del panel. Hoy la instalación nueva no tiene ninguna (se entra con la clave de administración); llevar su gestión al panel queda fuera de alcance.
- No hay papelera ni restauración, igual que con los documentos (feature 012).
- Cambiar el nombre de un programa o dominio, y mover dominios entre programas, quedan fuera de alcance.
- No se crean permisos nuevos: valen los alcances que ya existen (global y por programa).
- La eliminación de documentos y de carpetas vacías sigue funcionando como hoy.
- Para vaciar un dominio se usan las acciones que ya existen: eliminar documentos (también en bloque) y borrar carpetas vacías.
