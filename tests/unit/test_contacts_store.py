"""Almacén de contactos de WhatsApp (feature 017): estados, reclamo atómico, unicidad y filtros."""

from datetime import timedelta

import pytest
from sqlalchemy import func, select

from mia.contacts import store
from mia.contacts.store import ContactFilters, ContactNotFound, InvalidData, InvalidTransition
from mia.storage.models import Bot, WhatsAppContact, _now

TEL = "+50688887777"


@pytest.fixture
def bot(db):
    with db() as session:
        session.add_all([Bot(id="b1", name="Uno", kapso_number_id="111"), Bot(id="b2", name="Dos", kapso_number_id="222")])
        session.commit()
    return "b1"


@pytest.fixture
def session(db):
    with db() as s:
        yield s


def _contactos(session) -> int:
    return session.scalar(select(func.count()).select_from(WhatsAppContact))


def test_obtener_o_crear_devuelve_pendiente_y_luego_el_mismo(session, bot):
    primero = store.get_or_create(session, bot, TEL)
    segundo = store.get_or_create(session, bot, TEL)

    assert primero.status == "pendiente" and primero.name is None and primero.email is None
    assert primero.email_retried is False
    assert segundo.id == primero.id and _contactos(session) == 1


def test_una_carrera_por_crear_el_mismo_contacto_deja_una_sola_fila(session, bot, monkeypatch):
    existente = store.get_or_create(session, bot, TEL)
    real = store._find
    llamadas = []

    def _find_ciego_la_primera_vez(s, bot_id, phone):
        llamadas.append(1)
        return None if len(llamadas) == 1 else real(s, bot_id, phone)

    monkeypatch.setattr(store, "_find", _find_ciego_la_primera_vez)

    contacto = store.get_or_create(session, bot, TEL)

    assert contacto.id == existente.id and _contactos(session) == 1


def test_el_mismo_telefono_en_dos_bots_son_dos_contactos(session, bot):
    uno = store.get_or_create(session, "b1", TEL)
    dos = store.get_or_create(session, "b2", TEL)

    assert uno.id != dos.id and _contactos(session) == 2


def test_el_reclamo_solo_gana_desde_pendiente(session, bot):
    assert store.apply_event(session, bot, TEL, "claim_invite").claimed is True
    otra = store.apply_event(session, bot, TEL, "claim_invite")

    assert otra.claimed is False and otra.contact.status == "invitada"


def test_el_reclamo_atomico_lo_gana_una_sola_sesion(db, bot):
    with db() as a, db() as b:
        contacto = store.get_or_create(a, bot, TEL)
        assert store.claim_invite(a, contacto.id) is True
        assert store.claim_invite(b, contacto.id) is False


def test_liberar_la_invitacion_vuelve_a_pendiente_solo_sin_datos(session, bot):
    store.apply_event(session, bot, TEL, "claim_invite")
    assert store.apply_event(session, bot, TEL, "release_invite").contact.status == "pendiente"

    store.apply_event(session, bot, TEL, "claim_invite")
    store.apply_event(session, bot, TEL, "provided", name="Ana Pérez")
    store.apply_event(session, bot, TEL, "reopen")
    with pytest.raises(InvalidTransition):
        store.apply_event(session, bot, TEL, "release_invite")


def test_entregar_guarda_en_minusculas_y_reemplaza_solo_lo_recibido(session, bot):
    store.apply_event(session, bot, TEL, "claim_invite")

    r = store.apply_event(session, bot, TEL, "provided", name="  Ana Pérez ", email="Ana@Correo.COM")

    assert (r.contact.status, r.contact.name, r.contact.email) == ("entrego", "Ana Pérez", "ana@correo.com")
    store.apply_event(session, bot, TEL, "reopen")
    r = store.apply_event(session, bot, TEL, "provided", email="otra@correo.com")
    assert (r.contact.name, r.contact.email, r.contact.status) == ("Ana Pérez", "otra@correo.com", "entrego")


def test_entregar_exige_al_menos_un_dato_y_validos(session, bot):
    store.apply_event(session, bot, TEL, "claim_invite")
    for datos in (
        {},
        {"name": "   "},
        {"name": "x" * 81},
        {"name": "dos\nlíneas"},
        {"email": "ana@"},
        {"email": "ana@correo"},
        {"email": "a b@correo.com"},
        {"email": "a" * 250 + "@c.com"},
    ):
        with pytest.raises(InvalidData) as error:
            store.apply_event(session, bot, TEL, "provided", **datos)
        # El mensaje nunca repite lo recibido.
        for valor in datos.values():
            assert valor.strip() not in str(error.value) or not valor.strip()
    assert store.get_or_create(session, bot, TEL).status == "invitada"


def test_el_nombre_puede_tener_80_caracteres(session, bot):
    store.apply_event(session, bot, TEL, "claim_invite")
    r = store.apply_event(session, bot, TEL, "provided", name="n" * 80)
    assert len(r.contact.name) == 80


def test_reintento_de_correo_solo_una_vez_y_guarda_el_nombre(session, bot):
    store.apply_event(session, bot, TEL, "claim_invite")

    r = store.apply_event(session, bot, TEL, "email_retry", name="Ana Pérez")

    assert (r.contact.status, r.contact.email_retried, r.contact.name) == ("invitada", True, "Ana Pérez")
    with pytest.raises(InvalidTransition):
        store.apply_event(session, bot, TEL, "email_retry")


def test_declinar_deja_declino_o_entrego_si_ya_habia_un_dato(session, bot):
    store.apply_event(session, bot, TEL, "claim_invite")
    assert store.apply_event(session, bot, TEL, "declined").contact.status == "declino"

    otro = "+50670001111"
    store.apply_event(session, bot, otro, "claim_invite")
    store.apply_event(session, bot, otro, "email_retry", name="Luis Mora")
    assert store.apply_event(session, bot, otro, "declined").contact.status == "entrego"


def test_declinar_dos_veces_no_falla(session, bot):
    store.apply_event(session, bot, TEL, "claim_invite")
    store.apply_event(session, bot, TEL, "declined")
    assert store.apply_event(session, bot, TEL, "declined").contact.status == "declino"


def test_borrar_los_datos_los_deja_nulos_y_dice_si_habia(session, bot):
    store.apply_event(session, bot, TEL, "claim_invite")
    store.apply_event(session, bot, TEL, "provided", name="Ana Pérez", email="ana@correo.com")

    r = store.apply_event(session, bot, TEL, "erase")

    assert r.had_data is True
    assert (r.contact.name, r.contact.email, r.contact.status, r.contact.email_retried) == (None, None, "declino", False)
    assert store.apply_event(session, bot, TEL, "erase").had_data is False


def test_borrar_crea_el_contacto_si_falta_y_funciona_en_cualquier_estado(session, bot):
    r = store.apply_event(session, bot, "+50611112222", "erase")
    assert (r.had_data, r.contact.status) == (False, "declino")


def test_reabrir_funciona_desde_cualquier_estado_y_conserva_los_datos(session, bot):
    store.apply_event(session, bot, TEL, "claim_invite")
    store.apply_event(session, bot, TEL, "provided", email="ana@correo.com")

    r = store.apply_event(session, bot, TEL, "reopen")
    assert (r.claimed, r.contact.status, r.contact.email) == (True, "invitada", "ana@correo.com")

    # Desde pendiente (persona que aún no fue invitada) y desde invitada (repite la invitación) también.
    nuevo = "+50699998888"
    assert store.apply_event(session, bot, nuevo, "reopen").contact.status == "invitada"
    assert store.apply_event(session, bot, nuevo, "reopen").claimed is True


def test_reabrir_reinicia_el_reintento_de_correo(session, bot):
    store.apply_event(session, bot, TEL, "claim_invite")
    store.apply_event(session, bot, TEL, "email_retry")
    r = store.apply_event(session, bot, TEL, "reopen")
    assert r.contact.email_retried is False


def test_un_evento_fuera_de_orden_lanza_con_el_estado_actual(session, bot):
    store.get_or_create(session, bot, TEL)
    with pytest.raises(InvalidTransition) as error:
        store.apply_event(session, bot, TEL, "provided", name="Ana Pérez")
    assert error.value.status == "pendiente"


def test_los_eventos_que_exigen_contacto_lanzan_si_no_existe(session, bot):
    for evento in ("release_invite", "provided", "email_retry", "declined"):
        with pytest.raises(ContactNotFound):
            store.apply_event(session, bot, TEL, evento, name="Ana Pérez")


def test_evento_desconocido(session, bot):
    with pytest.raises(InvalidData):
        store.apply_event(session, bot, TEL, "inventado")


def test_last_seen_se_actualiza_como_maximo_una_vez_por_hora(session, bot):
    contacto = store.get_or_create(session, bot, TEL)
    inicial = contacto.last_seen_at

    store.touch(session, contacto, now=inicial + timedelta(minutes=30))
    assert store.get_or_create(session, bot, TEL).last_seen_at == inicial

    store.touch(session, contacto, now=inicial + timedelta(minutes=61))
    assert store.get_or_create(session, bot, TEL).last_seen_at == inicial + timedelta(minutes=61)


def _poblar(session):
    """b1: A pendiente; B entrego con correo; C declino. b2: D entrego con solo nombre."""
    ahora = _now()
    filas = [
        ("b1", "+50610000001", None, None, "pendiente", 0),
        ("b1", "+50610000002", "Beto", "beto@correo.com", "entrego", 1),
        ("b1", "+50610000003", None, None, "declino", 2),
        ("b2", "+50610000004", "Dani", None, "entrego", 3),
    ]
    for i, (bot_id, tel, nombre, correo, estado, minutos) in enumerate(filas):
        session.add(
            WhatsAppContact(
                id=f"c{i}", bot_id=bot_id, phone=tel, name=nombre, email=correo, status=estado,
                created_at=ahora + timedelta(minutes=minutos), last_seen_at=ahora, updated_at=ahora,
            )
        )
    session.commit()


def test_lista_de_la_mas_reciente_a_la_mas_antigua_y_paginada(session, bot):
    _poblar(session)

    items, total = store.list_contacts(session, ContactFilters(), page=1, page_size=3)
    assert total == 4 and [c.id for c in items] == ["c3", "c2", "c1"]
    items, _ = store.list_contacts(session, ContactFilters(), page=2, page_size=3)
    assert [c.id for c in items] == ["c0"]


def test_filtros_por_bot_estado_y_correo_combinan(session, bot):
    _poblar(session)

    def ids(**filtros):
        return sorted(c.id for c in store.list_contacts(session, ContactFilters(**filtros), 1, 50)[0])

    assert ids(bot_id="b2") == ["c3"]
    assert ids(statuses=["entrego"]) == ["c1", "c3"]
    assert ids(statuses=["pendiente", "declino"]) == ["c0", "c2"]
    assert ids(has_email=True) == ["c1"]
    assert ids(has_email=False) == ["c0", "c2", "c3"]
    assert ids(bot_id="b1", statuses=["entrego"], has_email=True) == ["c1"]


def test_el_resumen_por_estado_ignora_el_filtro_de_estado_pero_no_los_demas(session, bot):
    _poblar(session)

    todo = store.summary(session, ContactFilters(statuses=["declino"]))
    assert todo == {"pendiente": 1, "invitada": 0, "entrego": 2, "declino": 1}
    assert store.summary(session, ContactFilters(bot_id="b1"))["entrego"] == 1


def test_borrar_uno_y_borrar_por_filtro_respetan_el_filtro(session, bot):
    _poblar(session)

    assert store.delete_contact(session, "c0") is True
    assert store.delete_contact(session, "c0") is False

    assert store.count(session, ContactFilters(bot_id="b1", statuses=["entrego"])) == 1
    assert store.delete_filtered(session, ContactFilters(bot_id="b1", statuses=["entrego"])) == 1
    restantes = sorted(c.id for c in store.list_contacts(session, ContactFilters(), 1, 50)[0])
    assert restantes == ["c2", "c3"]
