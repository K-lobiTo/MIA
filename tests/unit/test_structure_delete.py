"""Eliminación de programas y dominios (feature 023). Contrato en
specs/023-eliminar-programas-dominios/contracts/eliminar-estructura-api.md."""

import json
from decimal import Decimal

import pytest
from sqlalchemy import event, select

from mia.access.scope import Principal
from mia.api.main import app
from mia.api.routes import artifacts as artifact_routes
from mia.api.routes import domains as domain_routes
from mia.api.routes import inventory as inventory_routes
from mia.api.routes import structure as structure_routes
from mia.api.security import require_admin
from mia.storage.models import (
    Admin,
    AdminUnit,
    Artifact,
    ArtifactDomain,
    ArtifactUnit,
    Bot,
    ConsultaUser,
    DeletedDomain,
    Document,
    Domain,
    Folder,
    QueryLog,
    Unit,
)
from mia.usage.log import detail


class Almacen:
    """Almacén de vectores simulado: {id del documento: id del dominio con que están etiquetados sus fragmentos}."""

    def __init__(self):
        self.fragmentos: dict[str, str] = {}
        self.caido = False

    def document_ids_in_domain(self, domain_id):
        if self.caido:
            raise ConnectionError("sin almacén")
        return {doc for doc, dominio in self.fragmentos.items() if dominio == domain_id}

    def delete_document(self, document_id):
        self.fragmentos.pop(document_id, None)

    def set_domain(self, document_id, domain_id):
        self.fragmentos[document_id] = domain_id


@pytest.fixture
def almacen(monkeypatch):
    store = Almacen()
    monkeypatch.setattr(structure_routes, "get_vector_store", lambda: store)
    return store


@pytest.fixture
def base(db):
    with db() as session:
        session.add_all(
            [
                Unit(id="p1", name="Computación"),
                Unit(id="p2", name="Analítica"),
                Domain(id="d1", unit_id="p1", name="Admisión"),
                Domain(id="d2", unit_id="p2", name="Cursos"),
            ]
        )
        session.commit()
    return db


def _artefacto(id_, nombre, **extra):
    return Artifact(id=id_, name=nombre, key_hash=f"h-{id_}", key_prefix="mia_x", **extra)


def _documento(id_, domain_id, status="done", **extra):
    return Document(id=id_, domain_id=domain_id, filename=f"{id_}.pdf", source_type="pdf", file_hash=id_, status=status, **extra)


def _agregar(db, *filas):
    with db() as session:
        for fila in filas:
            session.add(fila)
            session.flush()
        session.commit()


def _existe(db, modelo, id_):
    with db() as session:
        return session.get(modelo, id_) is not None


def _como(principal):
    app.dependency_overrides[require_admin] = lambda: principal


@pytest.fixture
def de_computacion():
    """Cuenta con alcance solo sobre el programa p1."""
    _como(Principal(email="coord@itcr.ac.cr", is_global=False, unit_ids=frozenset({"p1"}), source="entra"))
    yield
    app.dependency_overrides.pop(require_admin, None)


def _chequeo(client, admin, ruta):
    response = client.get(f"{ruta}/deletion", headers=admin)
    assert response.status_code == 200, response.text
    return response.json()


def _por_tipo(items):
    return {item["kind"]: item for item in items}


# --- Dominios (historia 1) ---


def test_un_dominio_vacio_se_elimina_y_su_nombre_queda_libre(client, admin, base, almacen):
    chequeo = _chequeo(client, admin, "/domains/d1")
    assert chequeo == {"name": "Admisión", "can_delete": True, "blockers": [], "affects": []}
    assert _existe(base, Domain, "d1")  # comprobar no cambia nada

    assert client.delete("/domains/d1", headers=admin).status_code == 204

    assert not _existe(base, Domain, "d1") and _existe(base, Domain, "d2")
    assert client.post("/domains", headers=admin, json={"unit_id": "p1", "name": "Admisión"}).status_code == 201
    assert client.delete("/domains/d1", headers=admin).status_code == 404


@pytest.mark.parametrize("estado", ["pending", "processing", "done", "error"])
def test_un_dominio_con_documentos_en_cualquier_estado_no_se_elimina(client, admin, base, almacen, estado):
    _agregar(base, _documento("doc", "d1", status=estado))

    chequeo = _chequeo(client, admin, "/domains/d1")
    response = client.delete("/domains/d1", headers=admin)

    assert chequeo["can_delete"] is False and _por_tipo(chequeo["blockers"])["documents"]["count"] == 1
    assert response.status_code == 409 and "1 documento" in response.json()["detail"]
    assert _existe(base, Domain, "d1") and _existe(base, Document, "doc")


def test_un_dominio_con_carpetas_no_se_elimina(client, admin, base, almacen):
    _agregar(base, Folder(id="f1", domain_id="d1", name="2026"), Folder(id="f2", domain_id="d1", parent_id="f1", name="Marzo"))

    response = client.delete("/domains/d1", headers=admin)

    assert response.status_code == 409 and "2 carpetas" in response.json()["detail"]
    assert _existe(base, Domain, "d1")


def test_los_accesos_puntuales_se_quitan_y_la_comprobacion_dice_a_quien_afecta(client, admin, base, almacen):
    _agregar(
        base,
        _artefacto("a1", "Consulta amplia"),
        _artefacto("a2", "Solo admisión"),
        ArtifactDomain(artifact_id="a1", domain_id="d1"),
        ArtifactDomain(artifact_id="a1", domain_id="d2"),
        ArtifactDomain(artifact_id="a2", domain_id="d1"),
        Bot(id="b1", name="Bot admisión", kapso_number_id="1", artifact_id="a2"),
    )

    afectados = _por_tipo(_chequeo(client, admin, "/domains/d1")["affects"])

    assert sorted(afectados["artifacts"]["names"]) == ["Consulta amplia", "Solo admisión"]
    assert afectados["empty_artifacts"]["names"] == ["Solo admisión"]
    assert afectados["bots"]["names"] == ["Bot admisión"]
    assert client.delete("/domains/d1", headers=admin).status_code == 204
    with base() as session:
        assert session.execute(select(ArtifactDomain.artifact_id, ArtifactDomain.domain_id)).all() == [("a1", "d2")]
        assert session.get(Artifact, "a2") is not None  # el artefacto sigue, sin nada que consultar


def test_quien_no_administra_un_programa_no_puede_eliminar_su_dominio(client, base, almacen, de_computacion, capsys):
    assert client.delete("/domains/d2").status_code == 403
    assert _existe(base, Domain, "d2")
    registro = capsys.readouterr().out
    assert "domain.delete" in registro and "rechazado" in registro

    assert client.delete("/domains/d1").status_code == 204


def test_los_artefactos_fuera_del_alcance_se_cuentan_pero_no_se_nombran(client, base, almacen, de_computacion):
    _agregar(
        base,
        _artefacto("a1", "Mía"),
        _artefacto("a2", "De otros"),
        ArtifactDomain(artifact_id="a1", domain_id="d1"),
        ArtifactDomain(artifact_id="a2", domain_id="d1"),
        ArtifactDomain(artifact_id="a2", domain_id="d2"),
    )

    artefactos = _por_tipo(_chequeo(client, {}, "/domains/d1")["affects"])["artifacts"]

    assert artefactos["count"] == 2 and artefactos["names"] == ["Mía"]


def test_una_clave_de_artefacto_o_sin_credenciales_no_elimina(client, base, almacen):
    assert client.delete("/domains/d1", headers={"X-Artifact-Key": "mia_x"}).status_code == 401
    assert client.delete("/units/p1").status_code == 401
    assert _existe(base, Domain, "d1")


def test_los_fragmentos_huerfanos_se_borran_y_los_de_otro_dominio_se_reetiquetan(client, admin, base, almacen):
    _agregar(base, _documento("vivo", "d2"))
    almacen.fragmentos = {"huerfano": "d1", "vivo": "d1", "otro": "d2"}

    assert client.delete("/domains/d1", headers=admin).status_code == 204

    assert almacen.fragmentos == {"vivo": "d2", "otro": "d2"}


def test_si_el_almacen_no_responde_no_cambia_nada(client, admin, base, almacen):
    _agregar(base, _artefacto("a1", "Consulta"), ArtifactDomain(artifact_id="a1", domain_id="d1"))
    almacen.caido = True

    response = client.delete("/domains/d1", headers=admin)

    assert response.status_code == 503
    assert _existe(base, Domain, "d1") and not _existe(base, DeletedDomain, "d1")
    with base() as session:
        assert session.scalars(select(ArtifactDomain.domain_id)).all() == ["d1"]
    almacen.caido = False
    assert client.delete("/domains/d1", headers=admin).status_code == 204


def test_la_eliminacion_queda_en_el_registro_de_administracion(client, admin, base, almacen, capsys):
    client.delete("/domains/d1", headers=admin)

    linea = [json.loads(x) for x in capsys.readouterr().out.splitlines() if "domain.delete" in x][-1]
    assert linea["target"] == "d1" and linea["detail"] == "Admisión" and linea["result"] == "ok"


def test_dominio_eliminado_durante_una_carga_responde_404_y_no_deja_archivo(client, admin, base, tmp_path, monkeypatch):
    engine = base.kw["bind"]
    # SQLite no aplica claves foráneas por defecto; Postgres sí.
    event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    engine.dispose()
    destino = tmp_path / "uploads"

    class DominioQueSeBorra(type(destino)):
        def mkdir(self, *args, **kwargs):
            super().mkdir(*args, **kwargs)
            with base() as session:
                session.delete(session.get(Domain, "d1"))
                session.commit()

    monkeypatch.setattr(domain_routes, "UPLOAD_DIR", DominioQueSeBorra(destino))
    monkeypatch.setattr(domain_routes, "ingest_document", lambda _: None)

    response = client.post("/domains/d1/documents", headers=admin, files={"file": ("a.txt", b"hola", "text/plain")})

    assert response.status_code == 404 and response.json()["detail"] == "El dominio ya no existe."
    assert list(destino.iterdir()) == []


# --- Programas (historia 2) ---


def test_un_programa_vacio_se_elimina_y_su_nombre_queda_libre(client, admin, base, almacen):
    client.delete("/domains/d1", headers=admin)
    assert _chequeo(client, admin, "/units/p1") == {"name": "Computación", "can_delete": True, "blockers": [], "affects": []}

    assert client.delete("/units/p1", headers=admin).status_code == 204

    assert not _existe(base, Unit, "p1") and _existe(base, Unit, "p2")
    assert client.delete("/units/p1", headers=admin).status_code == 404
    assert client.post("/units", headers=admin, json={"name": "Computación"}).status_code == 201


def test_un_programa_con_cosas_asociadas_no_se_elimina_y_nada_cambia(client, admin, base, almacen):
    _agregar(
        base,
        ConsultaUser(id="u1", username="ana", password_hash="x", unit_id="p1", created_by="t"),
        ConsultaUser(id="u2", username="beto", password_hash="x", unit_id="p1", active=False, created_by="t"),
        Admin(id="ad1", email="coord@itcr.ac.cr"),
        AdminUnit(admin_id="ad1", unit_id="p1"),
        _artefacto("a1", "Consulta Computación"),
        ArtifactUnit(artifact_id="a1", unit_id="p1"),
    )

    chequeo = _chequeo(client, admin, "/units/p1")
    response = client.delete("/units/p1", headers=admin)

    impedimentos = _por_tipo(chequeo["blockers"])
    assert set(impedimentos) == {"domains", "consulta_users", "admins", "artifacts"}
    assert impedimentos["domains"]["names"] == ["Admisión"]
    assert impedimentos["consulta_users"]["names"] == ["ana", "beto"]
    assert impedimentos["admins"]["names"] == ["coord@itcr.ac.cr"]
    assert impedimentos["artifacts"]["names"] == ["Consulta Computación"]
    assert response.status_code == 409 and _existe(base, Unit, "p1")
    with base() as session:
        assert session.get(ConsultaUser, "u1").unit_id == "p1"


def test_solo_el_alcance_global_elimina_programas(client, base, almacen, de_computacion, capsys):
    assert client.delete("/units/p1").status_code == 403
    assert client.get("/units/p1/deletion").status_code == 403
    assert _existe(base, Unit, "p1")
    assert "rechazado" in capsys.readouterr().out


def test_se_nombran_como_maximo_diez_pero_se_cuentan_todos(client, admin, base, almacen):
    _agregar(base, *[ConsultaUser(id=f"u{i}", username=f"persona{i:02}", password_hash="x", unit_id="p1", created_by="t") for i in range(13)])

    usuarios = _por_tipo(_chequeo(client, admin, "/units/p1")["blockers"])["consulta_users"]

    assert usuarios["count"] == 13 and len(usuarios["names"]) == 10


# --- Textos (historia 4) ---


def test_cada_impedimento_dice_como_resolverlo(client, admin, base, almacen):
    _agregar(
        base,
        ConsultaUser(id="u1", username="ana", password_hash="x", unit_id="p1", created_by="t"),
        Admin(id="ad1", email="coord@itcr.ac.cr"),
        AdminUnit(admin_id="ad1", unit_id="p1"),
        _artefacto("a1", "Consulta Computación"),
        ArtifactUnit(artifact_id="a1", unit_id="p1"),
    )

    pistas = {k: v["hint"] for k, v in _por_tipo(_chequeo(client, admin, "/units/p1")["blockers"]).items()}
    frase = client.delete("/units/p1", headers=admin).json()["detail"]

    assert "Usuarios de la Consulta" in pistas["consulta_users"]
    assert "soporte técnico" in pistas["admins"]
    assert "único acceso" in pistas["artifacts"] and "elimina el artefacto" in pistas["artifacts"] and "bot" in pistas["artifacts"]
    assert frase.startswith("No se puede eliminar todavía el programa")
    for esperado in ("1 dominio", "1 usuario de la Consulta", "ana", "1 cuenta de administración", "1 artefacto", "soporte técnico"):
        assert esperado in frase, esperado
    for tecnico in ("unit_id", "foreign", "409"):
        assert tecnico not in frase


# --- El historial y lo demás (historia 5) ---


def test_el_historial_sigue_nombrando_el_dominio_eliminado(client, admin, base, almacen):
    _agregar(base, QueryLog(id="q1", question="¿Fechas?", domain_ids=json.dumps(["d1", "d2"]), cost_usd=Decimal(0)))

    client.delete("/domains/d1", headers=admin)

    with base() as session:
        assert detail(session, session.get(QueryLog, "q1"))["domains"] == [
            "Computación / Admisión (eliminado)",
            "Analítica / Cursos",
        ]
        assert json.loads(session.get(QueryLog, "q1").domain_ids) == ["d1", "d2"]


def test_los_demas_artefactos_dominios_y_topes_no_cambian(client, admin, base, almacen):
    _agregar(
        base,
        _artefacto("a1", "Otra", modes="literal,razonamiento", daily_cap_usd=Decimal("0.75")),
        ArtifactUnit(artifact_id="a1", unit_id="p2"),
        _documento("doc", "d2"),
    )
    almacen.fragmentos = {"doc": "d2"}

    client.delete("/domains/d1", headers=admin)

    with base() as session:
        artefacto = session.get(Artifact, "a1")
        assert (artefacto.key_hash, artefacto.modes, artefacto.daily_cap_usd) == ("h-a1", "literal,razonamiento", Decimal("0.75"))
    assert _existe(base, Domain, "d2") and almacen.fragmentos == {"doc": "d2"}
    assert client.get("/artifacts", headers=admin).status_code == 200


def test_un_artefacto_sin_ningun_dominio_se_sigue_listando(client, admin, base, almacen):
    _agregar(base, _artefacto("a1", "Solo admisión"), ArtifactDomain(artifact_id="a1", domain_id="d1"))

    client.delete("/domains/d1", headers=admin)

    [artefacto] = client.get("/artifacts", headers=admin).json()["artifacts"]
    assert artefacto["allowed_domain_count"] == 0


def test_dominio_eliminado_al_crear_una_carpeta_responde_404(client, admin, base, monkeypatch):
    engine = base.kw["bind"]
    event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    engine.dispose()

    def borrar_y_no_encontrar_hermana(session, *args):
        with base() as otra:
            otra.delete(otra.get(Domain, "d1"))
            otra.commit()

    monkeypatch.setattr(inventory_routes, "_sibling", borrar_y_no_encontrar_hermana)

    response = client.post("/domains/d1/folders", headers=admin, json={"name": "2026"})

    assert response.status_code == 404 and response.json()["detail"] == "El dominio ya no existe."


# --- Guardar algo que apunta a lo que se acaba de eliminar (T028) ---


def _con_claves_foraneas(db):
    engine = db.kw["bind"]
    event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    engine.dispose()


def _borrar_antes_de(monkeypatch, modulo, nombre, db, modelo, id_):
    """Simula que otra persona elimina la fila justo antes de que la ruta siga con `nombre`."""
    original = getattr(modulo, nombre)

    def envoltura(*args, **kwargs):
        with db() as otra:
            otra.delete(otra.get(modelo, id_))
            otra.commit()
        return original(*args, **kwargs)

    monkeypatch.setattr(modulo, nombre, envoltura)


def test_crear_un_dominio_en_un_programa_recien_eliminado_responde_404(client, admin, base, monkeypatch):
    _agregar(base, Unit(id="p3", name="Vacío"))
    _con_claves_foraneas(base)
    _borrar_antes_de(monkeypatch, domain_routes, "ensure_unit", base, Unit, "p3")

    response = client.post("/domains", headers=admin, json={"unit_id": "p3", "name": "Nuevo"})

    assert response.status_code == 404 and response.json()["detail"] == "El programa ya no existe."


@pytest.mark.parametrize("accion", ["crear", "editar"])
@pytest.mark.parametrize("modelo,id_,campo", [(Domain, "d1", "domain_ids"), (Unit, "p3", "unit_ids")])
def test_guardar_un_artefacto_con_algo_recien_eliminado_responde_404_sin_cambiar_nada(
    client, admin, base, monkeypatch, accion, modelo, id_, campo
):
    _agregar(base, Unit(id="p3", name="Vacío"), _artefacto("a1", "Consulta"), ArtifactDomain(artifact_id="a1", domain_id="d2"))
    _con_claves_foraneas(base)
    _borrar_antes_de(monkeypatch, artifact_routes, "ensure_can_grant", base, modelo, id_)
    acceso = {"all_domains": False, "unit_ids": [], "domain_ids": [], campo: [id_]}

    if accion == "crear":
        cuerpo = {"name": "Otra", "modes": ["literal"], "daily_cap_usd": 0.5, "access": acceso}
        response = client.post("/artifacts", headers=admin, json=cuerpo)
    else:
        response = client.patch("/artifacts/a1", headers=admin, json={"access": acceso})

    assert response.status_code == 404, response.text
    assert response.json()["detail"].startswith("Un programa o dominio elegido ya no existe.")
    with base() as session:
        assert session.scalars(select(Artifact.name)).all() == ["Consulta"]
        assert session.scalars(select(ArtifactDomain.domain_id)).all() == ["d2"]
