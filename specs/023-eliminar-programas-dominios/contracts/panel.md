# Contrato: panel

## Inventario

- Cada dominio tiene un botón **Eliminar**; cada programa, **Eliminar programa** (solo alcance global).
- Al pulsarlo se abre una ventana que consulta la comprobación:
  - **Con impedimentos**: título "No se puede eliminar todavía", una línea por impedimento (cantidad, nombres y qué hacer) y solo "Cerrar".
  - **Sin impedimentos**: nombra lo que se elimina, lista a quién afecta, dice "No se puede deshacer." y ofrece "Cancelar" y "Eliminar".
- Si `DELETE` falla, el mensaje se muestra en la misma ventana. Al terminar se refrescan inventario, artefactos y usuarios.
- Un dominio sin programa solo muestra el botón a quien tiene alcance global.

## Usuarios de la Consulta

- Cada usuario tiene **Cambiar programa**: lista desplegable con los programas del alcance y, solo con alcance global, "Ninguno (global)".
