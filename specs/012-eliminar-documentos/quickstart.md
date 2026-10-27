# Quickstart: validar la eliminación de documentos

Guía para comprobar la feature, de lo más barato (pruebas automáticas) a lo real (producción, solo con tu autorización). Diseño en [research.md](research.md), [data-model.md](data-model.md) y [contracts/](contracts/). Todo el desarrollo se hace en `dev`.

## 0. Prerrequisitos

```bash
source .venv/bin/activate && pip install -e ".[dev]" && pip install -e "./whatsapp[dev]"
docker compose up -d qdrant           # Qdrant local
cd web/admin && npm ci && cd ../..    # solo si se prueba el panel
```

## 1. Pruebas automáticas (sin red y sin cuota)

```bash
pytest tests/unit/test_removal.py tests/unit/test_documents_delete.py tests/unit/test_documents_bulk_delete.py
pytest tests/unit/test_ingestion_cancel.py tests/unit/test_usage_after_delete.py tests/unit/test_vector_store.py
pytest tests/integration/test_delete_document_qdrant.py    # se omite sola si no hay Qdrant local
pytest && ruff check src tests scripts whatsapp
cd web/admin && npm run typecheck && npm test && npm run build
```

Lo que deben demostrar:

- **Servicio y ruta**: elimina base, imágenes, fragmentos y archivo; 404 al repetir; alcance por programa con rechazo registrado; una clave de artefacto no elimina; auditoría `document.delete` con nombre y dominio, sin contenido.
- **Orden y fallas**: si falla el almacén de vectores, el documento y sus imágenes siguen intactos (503) y el reintento funciona; si el borrado de fragmentos deja alguno, no se confirma; si el archivo original no existe, la eliminación no falla.
- **Ingesta**: un documento en cola o procesándose se elimina sin dejar fragmentos (la ingesta se detiene por lote y al terminar), y la ingesta no falla al encontrar la fila ausente; un documento `processing` que no suelta el cerrojo da 409 sin tocar nada.
- **Lote**: resultado por documento, fallos parciales, alcance por documento entre dominios, repetidos contados una vez y tope de 100.
- **Sin efectos colaterales**: el historial de Uso (listado, detalle y CSV) es idéntico antes y después; volver a subir el mismo archivo responde 201 (también en otro dominio); el dominio y la carpeta siguen existiendo; los demás documentos siguen respondiendo; `/media/{public_id}` responde 404.
- **De punta a punta**: un documento citado por el bot de WhatsApp, eliminado, y la pregunta siguiente responde "sin información".
- **Panel**: selección, confirmación (nombres, imágenes, "no se puede deshacer"), resultado con fallos y reintento.

## 2. Recorrer el flujo en la laptop

```bash
ADMIN_KEY=admin-local uvicorn mia.api.main:app --reload     # API con Qdrant local
cd web/admin && npm run dev                                   # panel
```

1. En el panel, subir dos documentos de prueba a un dominio (por ejemplo `scripts/datos/`), esperar a `done` y asociar una imagen a uno.
2. Hacer en **Consulta** una pregunta que solo responda el primero: responde y cita su nombre.
3. En el Inventario, **Eliminar** ese documento: la confirmación muestra su nombre, la imagen y el aviso de que no se puede deshacer. Confirmar.
4. Repetir la pregunta: ahora "sin información" (SC-001). El Inventario ya no lo lista y `/media/<public_id>` da 404.
5. En el módulo **Uso**, la consulta del paso 2 sigue ahí, con el nombre del documento citado (FR-024).
6. Subir de nuevo el mismo archivo: entra como nuevo (no `already_existed`) y vuelve a responder (FR-020).
7. **Seleccionar** los dos documentos y **Eliminar seleccionados**: una sola confirmación, los dos desaparecen y los contadores del dominio bajan.
8. Con la ingesta lenta (`INGESTION_ENABLED=true` y un PDF grande), eliminar un documento mientras está `processing`: la confirmación avisa que se cancela su procesamiento, el documento desaparece y, al terminar, no queda ningún fragmento (comprobarlo en el Qdrant local, por ejemplo con `count_chunks` del documento).
9. Con un administrador de programa (alcance por programa), intentar eliminar un documento de otro programa: 403 y línea `rechazado` en el registro.
10. Detener Qdrant (`docker compose stop qdrant`) y eliminar un documento: 503 y el documento sigue visible; encenderlo y reintentar: se elimina.

## 3. Medir

| Criterio | Cómo se mide |
|---|---|
| SC-001, deja de responder | Pasos 2 a 4 con el documento citado: sin información desde la consulta siguiente, con el bot de WhatsApp y con la Consulta. |
| SC-004, tiempo | Cronometrar la eliminación de un documento de unos 200 fragmentos: menos de 10 s (en la práctica, un par de segundos). |
| Sin restos | Después de eliminar, `count_chunks(document_id)` da 0, no hay filas en `document_images` ni en `documents`, y el archivo de `uploads/` no existe. |
| SC-008, historial | La prueba de Uso y el paso 5. |

## 4. Producción (solo con tu autorización)

Es la forma real de quitar los documentos de prueba del bot (por ejemplo, `Maestria_en_Ciberseguridad.txt` y su complemento en "Apertura de promoción"):

1. Merge de `dev` a `main` y `git push origin main`.
2. `python scripts/servicios.py encender MIA --forzar` (y el panel). No hay migraciones nuevas: la cabeza sigue en `0007`, así que no hay riesgo de desplegar una versión con menos migraciones que la base.
3. En el panel, eliminar los documentos y comprobar que el bot responde "sin información" a lo que antes respondía.

**Volver atrás**: desplegar la versión anterior de la API basta (no hay migraciones que revertir). Un documento eliminado no se recupera: se vuelve a subir el archivo original y se asocian de nuevo sus imágenes (OPERACION.md, sección que la implementación agrega).
