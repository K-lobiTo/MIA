from mia.storage.models import Artifact, ArtifactDomain, ArtifactUnit, Domain, Unit


def _unidad(db, id_="u1", nombre="Computación"):
    with db() as session:
        session.add(Unit(id=id_, name=nombre, description=""))
        session.commit()


def _artefacto(db, id_, nombre, *, activo=True, todos=False, unidades=(), dominios=()):
    with db() as session:
        session.add(
            Artifact(id=id_, name=nombre, key_hash=f"hash-{id_}", key_prefix="mia_xxxx", active=activo, all_domains=todos)
        )
        session.flush()
        session.add_all([ArtifactUnit(artifact_id=id_, unit_id=u) for u in unidades])
        session.add_all([ArtifactDomain(artifact_id=id_, domain_id=d) for d in dominios])
        session.commit()


def test_crear_unidad_exige_clave_de_administracion(client, db, admin):
    assert client.post("/units", json={"name": "Computación"}).status_code == 401
    assert client.post("/units", json={"name": "Computación"}, headers={"X-Admin-Key": "otra"}).status_code == 401


def test_crear_unidad(client, db, admin):
    response = client.post("/units", json={"name": "Computación", "description": "Posgrados"}, headers=admin)

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Computación" and body["description"] == "Posgrados" and body["id"]
    assert [u["name"] for u in client.get("/units").json()] == ["Computación"]


def test_unidad_con_nombre_repetido_responde_409(client, db, admin):
    client.post("/units", json={"name": "Computación"}, headers=admin)

    response = client.post("/units", json={"name": "Computación"}, headers=admin)

    assert response.status_code == 409
    assert "Computación" in response.json()["detail"]


def test_unidad_sin_nombre_responde_422(client, db, admin):
    assert client.post("/units", json={"name": "   "}, headers=admin).status_code == 422
    assert client.post("/units", json={"name": ""}, headers=admin).status_code == 422


def test_crear_dominio_exige_clave_y_unidad(client, db, admin):
    _unidad(db)
    assert client.post("/domains", json={"unit_id": "u1", "name": "Currículum"}).status_code == 401
    assert client.post("/domains", json={"name": "Currículum"}, headers=admin).status_code == 422


def test_crear_dominio_en_una_unidad(client, db, admin):
    _unidad(db)

    response = client.post(
        "/domains", json={"unit_id": "u1", "name": "Currículum", "description": "Planes"}, headers=admin
    )

    assert response.status_code == 201
    body = response.json()
    assert body["unit_id"] == "u1" and body["name"] == "Currículum" and body["description"] == "Planes"
    assert body["visible_to"] == {"now": [], "needs_enabling": []}


def test_dominio_en_unidad_inexistente_responde_404(client, db, admin):
    response = client.post("/domains", json={"unit_id": "no-existe", "name": "X"}, headers=admin)
    assert response.status_code == 404


def test_nombre_de_dominio_repetido_en_la_unidad_responde_409_pero_no_en_otra(client, db, admin):
    _unidad(db, "u1", "Computación")
    _unidad(db, "u2", "Administración de Empresas")
    assert client.post("/domains", json={"unit_id": "u1", "name": "Currículum"}, headers=admin).status_code == 201

    repetido = client.post("/domains", json={"unit_id": "u1", "name": "Currículum"}, headers=admin)
    otra_unidad = client.post("/domains", json={"unit_id": "u2", "name": "Currículum"}, headers=admin)

    assert repetido.status_code == 409
    assert otra_unidad.status_code == 201


def test_visible_to_indica_que_artefactos_ven_el_dominio_nuevo(client, db, admin):
    _unidad(db, "u1", "Computación")
    _unidad(db, "u2", "Administración de Empresas")
    with db() as session:
        session.add(Domain(id="d-viejo", unit_id="u1", name="Viejo", description=""))
        session.commit()
    _artefacto(db, "a-todos", "Ve todo", todos=True)
    _artefacto(db, "a-unidad", "Ve Computación", unidades=["u1"])
    _artefacto(db, "a-otra", "Ve Administración", unidades=["u2"])
    _artefacto(db, "a-puntual", "Un dominio", dominios=["d-viejo"])
    _artefacto(db, "a-apagado", "Desactivado", activo=False, todos=True)

    response = client.post("/domains", json={"unit_id": "u1", "name": "Nuevo"}, headers=admin)

    visible = response.json()["visible_to"]
    assert sorted(visible["now"]) == ["Ve Computación", "Ve todo"]
    assert sorted(visible["needs_enabling"]) == ["Un dominio", "Ve Administración"]


def test_listar_dominios_incluye_la_unidad(client, db):
    _unidad(db)
    with db() as session:
        session.add(Domain(id="d1", unit_id="u1", name="Currículum", description=""))
        session.add(Domain(id="d2", unit_id=None, name="Suelto", description=""))
        session.commit()

    body = {d["name"]: d for d in client.get("/domains").json()}

    assert body["Currículum"]["unit_id"] == "u1" and body["Currículum"]["unit_name"] == "Computación"
    assert body["Suelto"]["unit_id"] is None and body["Suelto"]["unit_name"] is None
