import pytest

from mia.storage.models import Document, Domain, Folder, Unit


@pytest.fixture
def base(db):
    with db() as session:
        session.add(Unit(id="u1", name="Computación", description=""))
        session.add_all(
            [
                Domain(id="d1", unit_id="u1", name="Currículum", description=""),
                Domain(id="d2", unit_id="u1", name="Docentes", description=""),
            ]
        )
        session.commit()


def _crear(client, admin, dominio="d1", nombre="Programas", padre=None):
    return client.post(f"/domains/{dominio}/folders", json={"name": nombre, "parent_id": padre}, headers=admin)


def test_las_operaciones_de_carpetas_exigen_clave(client, admin, base):
    # `admin` configura ADMIN_KEY en la instancia; estas peticiones no la envían.
    assert client.post("/domains/d1/folders", json={"name": "X"}).status_code == 401
    assert client.patch("/folders/f", json={"name": "X"}).status_code == 401
    assert client.delete("/folders/f").status_code == 401


def test_crear_carpeta_en_la_raiz_y_anidada(client, admin, base):
    raiz = _crear(client, admin)
    assert raiz.status_code == 201
    assert raiz.json()["name"] == "Programas" and raiz.json()["parent_id"] is None

    hija = _crear(client, admin, nombre="2025", padre=raiz.json()["id"])

    assert hija.status_code == 201 and hija.json()["parent_id"] == raiz.json()["id"]


def test_nombre_repetido_en_el_mismo_nivel_responde_409_incluida_la_raiz(client, admin, base):
    raiz = _crear(client, admin)
    assert _crear(client, admin).status_code == 409  # la raíz tiene parent_id nulo: lo verifica la API
    assert _crear(client, admin, nombre="2025", padre=raiz.json()["id"]).status_code == 201
    assert _crear(client, admin, nombre="2025", padre=raiz.json()["id"]).status_code == 409


def test_el_mismo_nombre_en_otro_nivel_o_dominio_es_valido(client, admin, base):
    raiz = _crear(client, admin)
    assert _crear(client, admin, nombre="Programas", padre=raiz.json()["id"]).status_code == 201
    assert _crear(client, admin, dominio="d2").status_code == 201


def test_carpeta_en_dominio_o_padre_inexistente_responde_404(client, admin, base):
    assert _crear(client, admin, dominio="no-existe").status_code == 404
    assert _crear(client, admin, padre="no-existe").status_code == 404


def test_carpeta_padre_de_otro_dominio_responde_422(client, admin, base):
    otra = _crear(client, admin, dominio="d2", nombre="Otra")

    response = _crear(client, admin, dominio="d1", nombre="Hija", padre=otra.json()["id"])

    assert response.status_code == 422


def test_renombrar_carpeta(client, admin, base):
    carpeta = _crear(client, admin).json()

    response = client.patch(f"/folders/{carpeta['id']}", json={"name": "Cursos"}, headers=admin)

    assert response.status_code == 200 and response.json()["name"] == "Cursos"


def test_renombrar_a_un_nombre_que_ya_existe_en_el_nivel_responde_409(client, admin, base):
    _crear(client, admin, nombre="A")
    b = _crear(client, admin, nombre="B").json()

    assert client.patch(f"/folders/{b['id']}", json={"name": "A"}, headers=admin).status_code == 409
    # Conservar el mismo nombre no es un conflicto consigo misma.
    assert client.patch(f"/folders/{b['id']}", json={"name": "B"}, headers=admin).status_code == 200


def test_renombrar_carpeta_inexistente_responde_404(client, admin, base):
    assert client.patch("/folders/no-existe", json={"name": "X"}, headers=admin).status_code == 404


def test_borrar_carpeta_vacia(client, admin, base):
    carpeta = _crear(client, admin).json()

    assert client.delete(f"/folders/{carpeta['id']}", headers=admin).status_code == 204
    with_session = client.get("/inventory").json()
    assert with_session["units"][0]["domains"][0]["folders"] == []


def test_no_se_borra_una_carpeta_con_documentos_o_subcarpetas(client, admin, db, base):
    con_docs = _crear(client, admin, nombre="ConDocs").json()
    con_hijas = _crear(client, admin, nombre="ConHijas").json()
    _crear(client, admin, nombre="Hija", padre=con_hijas["id"])
    with db() as session:
        session.add(
            Document(id="doc1", domain_id="d1", folder_id=con_docs["id"], filename="a.pdf", source_type="pdf",
                     file_hash="h", status="done")
        )
        session.commit()

    for carpeta in (con_docs, con_hijas):
        response = client.delete(f"/folders/{carpeta['id']}", headers=admin)
        assert response.status_code == 409
        assert "vacía" in response.json()["detail"]
    with db() as session:
        assert session.get(Folder, con_docs["id"]) is not None


def test_borrar_carpeta_inexistente_responde_404(client, admin, base):
    assert client.delete("/folders/no-existe", headers=admin).status_code == 404
