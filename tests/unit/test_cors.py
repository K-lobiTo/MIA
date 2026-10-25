"""CORS: todo método HTTP que usan las rutas de la API está permitido para los sitios estáticos (panel y Consulta)."""

from mia.api.main import CORS_ALLOW_METHODS, app


def test_todos_los_metodos_de_las_rutas_estan_permitidos_por_cors():
    """Una ruta con un verbo nuevo (como el PUT de las imágenes) no puede quedar bloqueada por CORS cuando el panel, un
    sitio estático en otro origen, la llama: el navegador rechazaría la petición previa."""
    # El esquema OpenAPI lista cada ruta con sus métodos sin depender de cómo FastAPI agrupe los routers por dentro.
    usados = {method.upper() for operations in app.openapi()["paths"].values() for method in operations}
    usados -= {"HEAD", "OPTIONS"}

    assert usados, "no se encontraron rutas"
    assert usados <= set(CORS_ALLOW_METHODS), sorted(usados - set(CORS_ALLOW_METHODS))


def test_put_esta_permitido_para_las_rutas_de_imagenes():
    assert "PUT" in CORS_ALLOW_METHODS
