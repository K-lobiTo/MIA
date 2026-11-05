"""Contraseñas y nombres de usuario de la Consulta (feature 015, research R1)."""

import base64
import hashlib

from mia.chat import passwords
from mia.config import settings


def test_el_hash_lleva_los_parametros_y_una_sal_propia_y_no_contiene_la_contrasena():
    uno = passwords.hash_password("una contraseña larga")
    otro = passwords.hash_password("una contraseña larga")

    partes = uno.split("$")
    assert partes[0] == "scrypt" and partes[1:4] == ["16384", "8", "1"]
    assert len(base64.b64decode(partes[4])) == 16 and len(base64.b64decode(partes[5])) == 32
    assert uno != otro  # sal propia en cada contraseña
    assert "una contraseña larga" not in uno


def test_verify_acepta_la_correcta_y_rechaza_la_incorrecta_y_los_hashes_mal_formados():
    guardado = passwords.hash_password("correcta-123456")

    assert passwords.verify_password("correcta-123456", guardado) is True
    assert passwords.verify_password("incorrecta-123456", guardado) is False
    for roto in ["", "texto", "scrypt$a$b$c$d$e", "bcrypt$1$2$3$4$5", "scrypt$16384$8$1$!!$!!"]:
        assert passwords.verify_password("correcta-123456", roto) is False


def test_verify_usa_los_parametros_guardados_en_el_propio_texto():
    sal = b"0123456789abcdef"
    crudo = hashlib.scrypt(b"clave-de-prueba", salt=sal, n=2**13, r=8, p=1, dklen=32)
    antiguo = f"scrypt$8192$8$1${base64.b64encode(sal).decode()}${base64.b64encode(crudo).decode()}"

    assert passwords.verify_password("clave-de-prueba", antiguo) is True
    assert passwords.verify_password("otra-clave-de-prueba", antiguo) is False


def test_needs_rehash_detecta_parametros_distintos_a_los_vigentes():
    vigente = passwords.hash_password("clave-de-prueba")
    sal = b"0123456789abcdef"
    crudo = hashlib.scrypt(b"clave-de-prueba", salt=sal, n=2**13, r=8, p=1, dklen=32)
    antiguo = f"scrypt$8192$8$1${base64.b64encode(sal).decode()}${base64.b64encode(crudo).decode()}"

    assert passwords.needs_rehash(vigente) is False
    assert passwords.needs_rehash(antiguo) is True
    assert passwords.needs_rehash("basura") is True


def test_la_contrasena_generada_cumple_el_minimo_y_cambia_en_cada_llamada():
    generadas = {passwords.generate_password() for _ in range(5)}

    assert len(generadas) == 5
    for clave in generadas:
        assert len(clave) == 16
        assert passwords.validate_password(clave) is None


def test_validate_password_rechaza_las_cortas_y_las_de_solo_espacios(monkeypatch):
    assert passwords.validate_password("corta") is not None
    assert passwords.validate_password("123456789") is not None  # 9 < 10
    assert passwords.validate_password("1234567890") is None
    assert passwords.validate_password(" " * 20) is not None
    monkeypatch.setattr(settings, "password_min_chars", 12)
    assert passwords.validate_password("1234567890") is not None
    assert "12" in passwords.validate_password("1234567890")


def test_el_nombre_de_usuario_se_normaliza_y_se_valida():
    assert passwords.normalize_username("  Ana.Perez ") == "ana.perez"
    for bueno in ["ana", "ana.perez", "a_b-c.9", "x" * 40]:
        assert passwords.validate_username(bueno) is None, bueno
    for malo in ["", "ab", "x" * 41, "ana perez", "ana@itcr.ac.cr", "añá", "ana/perez"]:
        assert passwords.validate_username(malo) is not None, malo


def test_dummy_hash_es_un_hash_valido_que_ninguna_contrasena_real_verifica():
    assert passwords.DUMMY_HASH.startswith("scrypt$")
    assert passwords.verify_password("cualquier-cosa-larga", passwords.DUMMY_HASH) is False
