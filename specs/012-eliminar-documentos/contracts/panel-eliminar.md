# Contrato: eliminar documentos en el panel

Comportamiento del Inventario (`web/admin/src/modules/inventario/`) para eliminar uno o varios documentos. Sigue las reglas de interfaz de [web/admin/README.md](../../../web/admin/README.md#interfaz-mantine) (componentes de Mantine, tema de `src/theme.ts`, sin grises). Decisiones en [research.md](../research.md) R6.

## Dónde aparece

| Elemento | Detalle |
|---|---|
| Botón **Eliminar** en cada fila de documento | Ícono de papelera, nombre accesible `Eliminar <archivo>`, junto al botón Imágenes. Abre la confirmación con ese documento. |
| Botón **Seleccionar** en la parte superior del Inventario | Activa el modo de selección y pasa a decir **Cancelar selección**. |
| Casilla en cada fila (solo en modo selección) | Marca el documento; la casilla de una carpeta o dominio marca todos sus documentos visibles. |
| Barra de selección (solo en modo selección) | `N seleccionados`, **Eliminar seleccionados** (desactivado con 0) y **Cancelar**. |

Todas las personas con acceso al Inventario ven los controles; la API hace cumplir el alcance (no hay permiso nuevo). Salir del modo de selección, cancelar o terminar una eliminación con éxito limpia la selección.

## La confirmación (`EliminarDocumentosDialog`)

Una sola ventana para uno o varios documentos. Contenido:

1. Título: `Eliminar documento` o `Eliminar N documentos`.
2. Lista de nombres (hasta 10; después `y N más`), cada uno con su dominio.
3. Cuántas imágenes asociadas se pierden en total (suma de `image_count` del inventario; se omite si es 0).
4. Aviso de lo que se pierde: el documento, sus imágenes y su contenido en las respuestas de **todos los artefactos, incluido el bot de WhatsApp**.
5. Aviso de que **no se puede deshacer**, y cómo recuperarlo: volver a subir el archivo original y asociar de nuevo las imágenes.
6. Si algún documento está en cola o procesándose, una nota: `Se cancelará su procesamiento.`
7. Botones: **Cancelar** (cierra sin hacer nada; también Escape y la X) y el de confirmar, de acción destructiva, que dice `Eliminar` o `Eliminar N documentos`.

El botón de confirmar queda desactivado y con indicador mientras la petición está en curso; la ventana no se puede cerrar por error en ese tiempo.

## Resultado

| Caso | Qué ocurre |
|---|---|
| Todo eliminado | La ventana se cierra, el inventario se actualiza (documentos, contadores) y aparece un aviso `Documento eliminado` o `N documentos eliminados`. |
| Falla un solo documento | La ventana sigue abierta con el motivo en lenguaje claro y un botón **Reintentar**: `fuera de tu alcance`, `se está procesando, intenta de nuevo en un momento` o `no se pudo quitar del almacén de búsqueda; sigue como estaba`. |
| Lote con fallos parciales | Los eliminados desaparecen del inventario y de la selección; la ventana lista solo los que fallaron, con su motivo, y permite reintentarlos. |
| Documento ya inexistente (404) | Se trata como eliminado: el inventario se recarga y no se muestra error. |
| Sin conexión o error inesperado | Mensaje de error genérico con **Reintentar**; nada se da por eliminado. |

## Datos del cliente

| Pieza | Detalle |
|---|---|
| `web/admin/src/api/documents.ts` | `useDeleteDocument()` (`DELETE /domains/{id}/documents/{id}`) y `useBulkDeleteDocuments()` (`POST /documents/bulk-delete`). Ambos invalidan `inventory` y `images` al terminar. |
| `seleccion.ts` | Funciones puras con pruebas: alternar un documento, marcar un conjunto, recortar la lista de nombres a 10 con `y N más`, sumar imágenes, armar el texto del aviso y traducir el `status` de cada resultado a su mensaje. |
| Estado de la selección | En `InventarioPage`, con el conjunto de ids; se descarta al cambiar de filtro que oculte documentos seleccionados o al salir del modo. |

## Pruebas del panel (Vitest)

- Utilidades de selección: alternar, marcar todo, recorte de nombres, suma de imágenes, mensajes por `status`.
- La ventana con un documento y con varios: muestra los nombres, las imágenes y los dos avisos; cancelar no llama a la API; confirmar llama a la ruta correcta (por documento o de lote) con los ids.
- Resultado con fallos: lista solo los fallidos con su motivo y permite reintentar; un 404 se trata como eliminado.
- El botón por fila y el modo de selección están presentes con sus nombres accesibles.
