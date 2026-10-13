"""SOLO DESARROLLO: servidor de identidad simulado para probar el inicio de sesión del panel sin el client ID del TEC.

Levanta dos servidores en esta misma máquina:
  - Un "Microsoft" simulado en https://localhost:9000 (certificado autofirmado que se genera al arrancar):
    ofrece cuentas de prueba, el flujo de código con PKCE y la renovación con refresh token, y firma los ID
    tokens con una clave RSA local con el emisor, el tenant y los claims que espera la API.
  - La API de MIA en http://localhost:8000 con una base SQLite temporal ya sembrada (dos programas con
    sus dominios, documentos, artefactos y consultas) y con esas claves de firma como únicas de confianza.

Nada de esto toca producción: la confianza en la clave simulada se inyecta aquí, en este proceso, y no
existe ninguna variable de configuración que la active en la API real. No forma parte del paquete mia.

Uso (ver specs/004-acceso-panel-tec/quickstart.md):
    python scripts/idp_simulado.py                    # IdP y API
    python scripts/idp_simulado.py --vigencia 120     # ID tokens de 2 minutos, para probar la renovación
    curl -sk https://localhost:9000/_token/coord.comp@itcr.ac.cr   # un ID token válido de esa cuenta (para curl)

Panel (otra terminal, en web/admin; el navegador debe aceptar el certificado autofirmado):
    VITE_ENTRA_CLIENT_ID=cliente-de-prueba \\
    VITE_ENTRA_AUTHORITY=https://localhost:9000/1119bb90-88ba-4894-b7f1-de26e129d977 npm run dev
Para simular que Microsoft revoca las sesiones: abrir https://localhost:9000/_revocar
"""

import argparse
import base64
import hashlib
import json
import os
import secrets
import sys
import tempfile
import threading
import time
import uuid
from datetime import UTC, datetime, timedelta
from html import escape
from pathlib import Path
from urllib.parse import urlencode

TENANT = "1119bb90-88ba-4894-b7f1-de26e129d977"  # el mismo valor por defecto de la API y del panel
CLIENT_ID = "cliente-de-prueba"
KID = "clave-simulada"
IDP_PORT = 9000
API_PORT = 8000
PANEL_ORIGIN = "http://localhost:3001"
CLAVE_ADMIN = "clave-de-administracion-simulada"  # para probar la entrada del panel con la clave de administración

# correo -> (nombre, programas de la lista de administradores o None si es global, ¿incluye segundo factor?)
# Las cuentas con programas None y "no listada" se manejan aparte.
CUENTAS = {
    "operador@itcr.ac.cr": ("Operador de MIA (global)", "global", True),
    "coord.comp@itcr.ac.cr": ("Coordinador de la Unidad de Postgrados de Computación", ["Unidad de Postgrados de Computación"], True),
    "ayudante.comp@itcr.ac.cr": ("Ayudante de la Unidad de Postgrados de Computación", ["Unidad de Postgrados de Computación"], True),
    "coord.adm@itcr.ac.cr": ("Coordinador del Área académica de Analítica de Negocios", ["Área académica de Analítica de Negocios"], True),
    "sinmfa@itcr.ac.cr": ("Listada pero sin segundo factor", ["Unidad de Postgrados de Computación"], False),
    "sinregistro@itcr.ac.cr": ("Cuenta del TEC que no está en la lista", None, True),
}


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


class Identidad:
    """Clave de firma, códigos y refresh tokens del IdP simulado."""

    def __init__(self, vigencia: int):
        from cryptography.hazmat.primitives.asymmetric import rsa

        self.vigencia = vigencia
        self.clave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.codigos: dict[str, dict] = {}
        self.refrescos: dict[str, str] = {}

    def id_token(self, correo: str, client_id: str = CLIENT_ID, nonce: str | None = None) -> str:
        import jwt

        nombre, _, mfa = CUENTAS.get(correo, (correo, None, True))
        ahora = int(time.time())
        claims = {
            "ver": "2.0",
            "iss": f"https://login.microsoftonline.com/{TENANT}/v2.0",
            "aud": client_id,
            "tid": TENANT,
            "sub": _b64(hashlib.sha256(correo.encode()).digest())[:22],
            "oid": str(uuid.uuid5(uuid.NAMESPACE_DNS, correo)),
            "name": nombre,
            "preferred_username": correo,
            "email": correo,
            "amr": ["pwd", "mfa"] if mfa else ["pwd"],
            "iat": ahora,
            "nbf": ahora,
            "exp": ahora + self.vigencia,
        }
        if nonce:
            claims["nonce"] = nonce
        return jwt.encode(claims, self.clave, algorithm="RS256", headers={"kid": KID})

    def claves_publicas(self):
        from jwt.algorithms import RSAAlgorithm

        class Fuente:
            def __init__(self, publica):
                self.publica = publica

            def get_key(self, kid):
                return self.publica if kid == KID else None

        jwk = json.loads(RSAAlgorithm.to_jwk(self.clave.public_key()))
        return Fuente(self.clave.public_key()), {"keys": [{**jwk, "kid": KID, "use": "sig", "alg": "RS256"}]}


PAGINA = """<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Microsoft (simulado)</title>
<style>body{{font-family:system-ui;max-width:460px;margin:40px auto;padding:0 16px}}a{{display:block;padding:12px;
border:1px solid #888;border-radius:8px;margin:8px 0;text-decoration:none;color:inherit}}small{{color:#666}}</style>
<h1>Iniciar sesión (simulado)</h1><p>Esto no es Microsoft: es el servidor de identidad de pruebas de MIA.</p>
{cuentas}<p><small>Cliente: {client}</small></p></html>"""


def crear_idp(identidad: Identidad):
    from fastapi import FastAPI, Form, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

    app = FastAPI(title="IdP simulado")
    app.add_middleware(CORSMiddleware, allow_origins=[PANEL_ORIGIN], allow_methods=["*"], allow_headers=["*"])

    @app.get("/{tenant}/v2.0/.well-known/openid-configuration")
    def configuracion(tenant: str):
        base = f"https://localhost:{IDP_PORT}/{tenant}"
        return {
            "issuer": f"https://login.microsoftonline.com/{TENANT}/v2.0",
            "authorization_endpoint": f"{base}/oauth2/v2.0/authorize",
            "token_endpoint": f"{base}/oauth2/v2.0/token",
            "jwks_uri": f"{base}/discovery/v2.0/keys",
        }

    @app.get("/{tenant}/discovery/v2.0/keys")
    def claves(tenant: str):
        return identidad.claves_publicas()[1]

    @app.get("/{tenant}/oauth2/v2.0/authorize")
    def authorize(tenant: str, request: Request):
        q = dict(request.query_params)
        modo = q.get("response_mode", "fragment")
        destino = q.get("redirect_uri", "")

        def volver(parametros: dict):
            separador = "?" if modo == "query" else "#"
            return RedirectResponse(f"{destino}{separador}{urlencode(parametros)}", status_code=302)

        if q.get("prompt") == "none":
            return volver({"error": "login_required", "error_description": "Sin sesión en el IdP simulado.", "state": q.get("state", "")})
        correo = q.get("cuenta")
        if correo not in CUENTAS:
            enlaces = []
            for mail, (nombre, _, mfa) in CUENTAS.items():
                href = escape(f"?{urlencode({**q, 'cuenta': mail})}")
                enlaces.append(f'<a href="{href}"><strong>{escape(nombre)}</strong><br><small>{mail}{"" if mfa else " (sin segundo factor)"}</small></a>')
            return HTMLResponse(PAGINA.format(cuentas="".join(enlaces), client=escape(q.get("client_id", ""))))
        codigo = secrets.token_urlsafe(24)
        identidad.codigos[codigo] = {
            "correo": correo,
            "challenge": q.get("code_challenge", ""),
            "nonce": q.get("nonce"),
            "client_id": q.get("client_id", CLIENT_ID),
            "redirect_uri": destino,
        }
        return volver({"code": codigo, "state": q.get("state", ""), "client_info": "1"})

    @app.post("/{tenant}/oauth2/v2.0/token")
    def token(
        tenant: str,
        grant_type: str = Form(...),
        client_id: str = Form(CLIENT_ID),
        code: str = Form(""),
        code_verifier: str = Form(""),
        refresh_token: str = Form(""),
    ):
        def error(texto: str, descripcion: str):
            return JSONResponse({"error": texto, "error_description": descripcion, "suberror": "bad_token"}, status_code=400)

        nonce = None
        if grant_type == "authorization_code":
            datos = identidad.codigos.pop(code, None)
            if datos is None:
                return error("invalid_grant", "Código desconocido o ya usado.")
            esperado = _b64(hashlib.sha256(code_verifier.encode()).digest())
            if esperado != datos["challenge"]:
                return error("invalid_grant", "PKCE no coincide.")
            correo, nonce = datos["correo"], datos["nonce"]
        elif grant_type == "refresh_token":
            correo = identidad.refrescos.get(refresh_token)
            if correo is None:
                return error("invalid_grant", "La sesión fue revocada.")
        else:
            return error("unsupported_grant_type", grant_type)
        nuevo = secrets.token_urlsafe(32)
        identidad.refrescos[nuevo] = correo
        identidad.refrescos.pop(refresh_token, None)
        info = {"uid": str(uuid.uuid5(uuid.NAMESPACE_DNS, correo)), "utid": TENANT}
        return {
            "token_type": "Bearer",
            "scope": "openid profile email",
            "expires_in": identidad.vigencia,
            "ext_expires_in": identidad.vigencia,
            "access_token": secrets.token_urlsafe(24),
            "id_token": identidad.id_token(correo, client_id, nonce),
            "refresh_token": nuevo,
            "client_info": _b64(json.dumps(info).encode()),
        }

    @app.get("/_token/{correo}")
    def token_de_prueba(correo: str):
        return HTMLResponse(identidad.id_token(correo), media_type="text/plain")

    @app.get("/_revocar")
    def revocar():
        identidad.refrescos.clear()
        return HTMLResponse("<p>Sesiones revocadas: la siguiente renovación en silencio fallará.</p>")

    return app


def _certificado(carpeta: Path) -> tuple[str, str]:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    clave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nombre = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    ahora = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(nombre)
        .issuer_name(nombre)
        .public_key(clave.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(ahora - timedelta(minutes=1))
        .not_valid_after(ahora + timedelta(days=2))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False)
        .sign(clave, hashes.SHA256())
    )
    ruta_cert, ruta_clave = carpeta / "cert.pem", carpeta / "clave.pem"
    ruta_cert.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    ruta_clave.write_bytes(
        clave.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()
        )
    )
    return str(ruta_cert), str(ruta_clave)


def sembrar(session_factory) -> None:
    """Datos de ejemplo: dos programas con dominio, carpeta, documentos, artefactos y consultas, y la lista de administradores."""
    from decimal import Decimal

    from mia.access.admins import add_admin
    from mia.access.keys import generate_key, hash_key, key_prefix
    from mia.storage.models import Artifact, ArtifactUnit, Document, Domain, Folder, QueryLog, Unit

    with session_factory() as s:
        unidades = {}
        for nombre in ("Unidad de Postgrados de Computación", "Área académica de Analítica de Negocios"):
            unidades[nombre] = Unit(id=str(uuid.uuid4()), name=nombre, description=f"Programa: {nombre}")
            s.add(unidades[nombre])
        s.flush()
        artefactos = []
        for nombre, unidad in unidades.items():
            dominio = Domain(id=str(uuid.uuid4()), unit_id=unidad.id, name="Currículum", description="Planes y programas")
            s.add(dominio)
            s.flush()
            carpeta = Folder(id=str(uuid.uuid4()), domain_id=dominio.id, name="Programas")
            s.add(carpeta)
            s.flush()
            for i in range(2):
                s.add(Document(id=str(uuid.uuid4()), domain_id=dominio.id, folder_id=carpeta.id,
                               filename=f"programa-{nombre[:4].lower()}-{i + 1}.pdf", source_type="pdf",
                               file_hash=uuid.uuid4().hex, status="done"))
            clave = generate_key()
            art = Artifact(id=str(uuid.uuid4()), name=f"Consulta {nombre}", key_hash=hash_key(clave),
                           key_prefix=key_prefix(clave), modes="literal,razonamiento", daily_cap_usd=Decimal("0.5"))
            s.add(art)
            s.flush()
            s.add(ArtifactUnit(artifact_id=art.id, unit_id=unidad.id))
            artefactos.append(art)
        clave = generate_key()
        general = Artifact(id=str(uuid.uuid4()), name="Consulta general (todos los dominios)", key_hash=hash_key(clave),
                           key_prefix=key_prefix(clave), all_domains=True, modes="literal", daily_cap_usd=Decimal("0.5"))
        s.add(general)
        s.flush()
        artefactos.append(general)
        base = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=1)
        for n, art in enumerate(artefactos * 3):
            s.add(QueryLog(id=str(uuid.uuid4()), artifact_id=art.id, created_at=base - timedelta(minutes=n * 7),
                           mode="literal", outcome="answered", model="modelo-simulado", cost_usd=Decimal("0.004"),
                           prompt_tokens=800, completion_tokens=120, latency_ms=2500,
                           question=f"Pregunta de ejemplo {n + 1} ({art.name})", domain_ids="[]", sources="[]"))
        s.commit()
        for correo, (_, alcance, _) in CUENTAS.items():
            if alcance == "global":
                add_admin(s, correo, is_global=True, unit_names=[])
            elif alcance:
                add_admin(s, correo, is_global=False, unit_names=alcance)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--vigencia", type=int, default=600, help="vigencia de los ID tokens en segundos (600)")
    args = parser.parse_args()

    # La configuración se lee al importar mia: se fija antes, con una base temporal y sin tocar producción.
    carpeta = Path(tempfile.mkdtemp(prefix="mia-idp-"))
    os.environ.update(
        DATABASE_URL=f"sqlite:///{carpeta}/simulado.db",
        ENTRA_CLIENT_ID=CLIENT_ID,
        ENTRA_TENANT_ID=TENANT,
        ENTRA_REQUIRE_MFA="true",
        CORS_ORIGINS=PANEL_ORIGIN,
        INGESTION_ENABLED="true",
        ADMIN_KEY=CLAVE_ADMIN,
    )
    identidad = Identidad(args.vigencia)
    import uvicorn

    from mia.api import security
    from mia.api.main import app as api
    from mia.api.routes import domains
    from mia.storage.db import SessionLocal, init_db

    init_db()
    sembrar(SessionLocal)
    fuente, _ = identidad.claves_publicas()
    api.dependency_overrides[security.get_key_source] = lambda: fuente
    # Sin modelo de embeddings ni Qdrant: la subida de documentos solo los deja en cola.
    domains.ingest_document = lambda document_id: None

    cert, clave = _certificado(carpeta)
    idp = uvicorn.Server(
        uvicorn.Config(crear_idp(identidad), host="127.0.0.1", port=IDP_PORT, ssl_certfile=cert, ssl_keyfile=clave, log_level="warning")
    )
    threading.Thread(target=idp.run, daemon=True).start()
    print(f"IdP simulado: https://localhost:{IDP_PORT} (certificado autofirmado)")
    print(f"API: http://localhost:{API_PORT} con la base temporal {carpeta}/simulado.db")
    print(f"Clave de administración del panel (alcance global): {CLAVE_ADMIN}")
    print(f"ID tokens de {args.vigencia} s. Cuentas de prueba:")
    for correo, (nombre, alcance, mfa) in CUENTAS.items():
        etiqueta = "global" if alcance == "global" else ", ".join(alcance) if alcance else "NO está en la lista"
        print(f"  {correo:28} {etiqueta}{'' if mfa else ' (token sin segundo factor)'}")
    # lifespan apagado: no se necesitan Qdrant ni el modelo de embeddings para esta prueba.
    uvicorn.run(api, host="127.0.0.1", port=API_PORT, log_level="warning", lifespan="off")
    return 0


if __name__ == "__main__":
    sys.exit(main())
