"""ADMIN_KEY como clave de automatización de los scripts: alcance global, y desactivable dejándola vacía."""

import pytest

RUTAS_DE_LECTURA = ["/inventory", "/units", "/domains", "/artifacts", "/usage", "/usage/queries"]


@pytest.mark.parametrize("ruta", RUTAS_DE_LECTURA)
def test_con_la_clave_de_automatizacion_se_lee_con_alcance_global(client, units, admin, ruta):
    assert client.get(ruta, headers=admin).status_code == 200


def test_la_clave_escribe_con_alcance_global(client, units, admin):
    assert client.post("/units", json={"name": "Nueva"}, headers=admin).status_code == 201
    response = client.post("/domains", json={"unit_id": units.comp, "name": "Dominio"}, headers=admin)
    assert response.status_code == 201
    response = client.post(
        "/artifacts", json={"name": "General", "modes": ["literal"], "access": {"all_domains": True}}, headers=admin
    )
    assert response.status_code == 201


def test_la_clave_ve_todas_las_unidades(client, units, admin):
    nombres = [u["name"] for u in client.get("/inventory", headers=admin).json()["units"]]
    assert sorted(nombres) == ["Administración de Empresas", "Computación"]


def test_el_perfil_con_la_clave_es_de_automatizacion(client, admin):
    assert client.get("/me", headers=admin).json() == {
        "email": None,
        "is_global": True,
        "units": [],
        "source": "automation",
    }


@pytest.mark.parametrize("ruta", RUTAS_DE_LECTURA)
def test_clave_incorrecta_es_401(client, admin, ruta):
    response = client.get(ruta, headers={"X-Admin-Key": "otra-clave"})
    assert response.status_code == 401 and response.json()["code"] == "unauthenticated"


@pytest.mark.parametrize("ruta", RUTAS_DE_LECTURA)
def test_con_admin_key_vacia_la_clave_esta_desactivada(client, admin, monkeypatch, ruta):
    from mia.config import settings

    clave = admin["X-Admin-Key"]
    monkeypatch.setattr(settings, "admin_key", "")
    response = client.get(ruta, headers={"X-Admin-Key": clave})
    # 401 como cualquier clave incorrecta: no se revela que la clave existe o está apagada.
    assert response.status_code == 401 and response.json()["code"] == "unauthenticated"
    assert client.get(ruta, headers={"X-Admin-Key": ""}).status_code == 401
