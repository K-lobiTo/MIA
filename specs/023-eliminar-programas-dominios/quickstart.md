# Quickstart: validar la feature

## Pruebas automáticas

```bash
source .venv/bin/activate
pytest tests/unit/test_structure_delete.py tests/unit/test_consulta_users_unit.py tests/unit/test_migrations.py
ruff check src tests scripts whatsapp
(cd web/admin && npm test && npm run build)
```

## De punta a punta en local

Con `docker compose up -d qdrant`, la API (`uvicorn mia.api.main:app`) con `ADMIN_KEY` y el panel (`npm run dev`):

1. Crear un programa y un dominio de prueba. "Eliminar programa" debe explicar que tiene un dominio.
2. Subir un documento al dominio: "Eliminar" debe pedir quitarlo primero.
3. Eliminar el documento; dar a un artefacto acceso a ese dominio; eliminar el dominio: la ventana nombra el artefacto.
4. Asignar un usuario de la Consulta al programa: impide eliminarlo. "Cambiar programa" a otro; eliminar el programa.
5. Crear de nuevo un programa con el mismo nombre.
6. En Uso, una consulta hecha sobre el dominio eliminado muestra su nombre con "(eliminado)".

## Despliegue

Hay migración (`0016`). Volver a una versión anterior exige `alembic downgrade 0015`.
