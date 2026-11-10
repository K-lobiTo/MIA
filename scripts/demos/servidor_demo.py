"""SOLO DESARROLLO: API y Microsoft simulado con datos FICTICIOS y claves conocidas, para grabar los videos de la guía de uso.

Reutiliza el Microsoft simulado de `scripts/idp_simulado.py` (certificado autofirmado, cuentas de prueba) y cambia la
siembra: programas, dominios, documentos, artefactos con claves fijas, usuarios de la Consulta, bots, consultas de los
últimos 30 días con calificaciones. No usa Qdrant ni el modelo de embeddings (`lifespan` apagado): las respuestas de
`POST /query` las pone el grabador (`scripts/demos/grabar.py`) y la ingesta de documentos se simula.

Uso (desde la raíz del repositorio, con el entorno de MIA activo):
    python scripts/demos/servidor_demo.py
"""

import json
import os
import sys
import tempfile
import threading
import time
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from random import Random

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import idp_simulado as idp

# Claves y usuarios conocidos: el grabador los escribe en las pantallas de entrada.
CLAVE_COMPUTACION = "mia_demo_computacion"
CLAVE_ANALITICA = "mia_demo_analitica"
CLAVE_GENERAL = "mia_demo_general"
USUARIO_CONSULTA = "estudiante.demo"
CLAVE_USUARIO = "ClaveDemo2026"

UNIDAD_COMP = "Unidad de Postgrados de Computación"
UNIDAD_ANAL = "Área académica de Analítica de Negocios"


def _doc(s, domain_id, folder_id, nombre, estado="done"):
    from mia.storage.models import Document

    s.add(
        Document(
            id=str(uuid.uuid4()),
            domain_id=domain_id,
            folder_id=folder_id,
            filename=nombre,
            source_type=nombre.rsplit(".", 1)[-1],
            file_hash=uuid.uuid4().hex,
            status=estado,
        )
    )


def sembrar_demo(session_factory) -> None:
    from mia.access.admins import add_admin
    from mia.access.keys import hash_key, key_prefix
    from mia.bots.usage import current_month
    from mia.chat.passwords import hash_password
    from mia.storage.models import (
        Artifact,
        ArtifactDomain,
        ArtifactUnit,
        Bot,
        BotMessageCount,
        ConsultaUser,
        Conversation,
        ConversationTurn,
        Domain,
        Folder,
        QueryLog,
        Unit,
    )

    azar = Random(2026)
    with session_factory() as s:
        unidades = {}
        for nombre in (UNIDAD_COMP, UNIDAD_ANAL):
            unidades[nombre] = Unit(id=str(uuid.uuid4()), name=nombre, description=f"Programa: {nombre}")
            s.add(unidades[nombre])
        s.flush()

        def dominio(unidad, nombre, descripcion, dinamico=False):
            d = Domain(
                id=str(uuid.uuid4()),
                unit_id=unidades[unidad].id,
                name=nombre,
                description=descripcion,
                dynamic=dinamico,
            )
            s.add(d)
            s.flush()
            return d

        def carpeta(d, nombre, padre=None):
            f = Folder(id=str(uuid.uuid4()), domain_id=d.id, parent_id=padre.id if padre else None, name=nombre)
            s.add(f)
            s.flush()
            return f

        # Computación
        curriculum = dominio(UNIDAD_COMP, "Currículum", "Planes de estudio y programas de curso")
        cursos = carpeta(curriculum, "Programas de curso")
        for n in ("Taller de Ejemplo A", "Taller de Ejemplo B", "Seminario de Ejemplo"):
            _doc(s, curriculum.id, cursos.id, f"Programa de curso {n}.pdf")
        _doc(s, curriculum.id, None, "Plan de estudios de ejemplo.pdf")
        consejo = dominio(UNIDAD_COMP, "Memoria del Consejo", "Actas de ejemplo del Consejo del programa")
        actas = carpeta(consejo, "Actas 2026")
        for n in (1, 2, 3):
            _doc(s, consejo.id, actas.id, f"Acta de ejemplo {n:02d}-2026.pdf")
        tesis = dominio(UNIDAD_COMP, "Proyectos de graduación: Tesis", "Reglamento y guías de la tesis")
        _doc(s, tesis.id, None, "Guía de tesis de ejemplo.docx")
        promo = dominio(UNIDAD_COMP, "Promoción", "Información vigente del periodo para promoción", dinamico=True)
        _doc(s, promo.id, None, "Calendario de ejemplo del periodo.txt")
        # Analítica
        curr_a = dominio(UNIDAD_ANAL, "Currículum", "Plan de estudios de la maestría")
        _doc(s, curr_a.id, None, "Plan de estudios de ejemplo (analítica).pdf")
        _doc(s, curr_a.id, None, "Programa de curso de ejemplo (analítica).pdf")
        s.commit()

        def artefacto(nombre, clave, **campos):
            art = Artifact(
                id=str(uuid.uuid4()),
                name=nombre,
                key_hash=hash_key(clave),
                key_prefix=key_prefix(clave),
                **campos,
            )
            s.add(art)
            s.flush()
            return art

        a_comp = artefacto(
            "Consulta Postgrados de Computación",
            CLAVE_COMPUTACION,
            description="Personal administrativo de la Unidad de Postgrados de Computación",
            modes="literal,razonamiento",
            daily_cap_usd=Decimal("0.5"),
            reasoning_daily_cap_usd=Decimal("0.2"),
            context_turns=2,
        )
        s.add(ArtifactUnit(artifact_id=a_comp.id, unit_id=unidades[UNIDAD_COMP].id))
        a_anal = artefacto(
            "Consulta Área Académica Analítica de Negocios",
            CLAVE_ANALITICA,
            description="Personal del Área académica de Analítica de Negocios (exige iniciar sesión)",
            modes="literal,razonamiento",
            daily_cap_usd=Decimal("0.5"),
            context_turns=3,
            require_login=True,
        )
        s.add(ArtifactUnit(artifact_id=a_anal.id, unit_id=unidades[UNIDAD_ANAL].id))
        a_bot = artefacto(
            "Artefacto del bot de WhatsApp",
            CLAVE_GENERAL,
            description="Dominios que el bot de WhatsApp puede consultar",
            modes="literal",
            daily_cap_usd=Decimal("0.3"),
        )
        s.add(ArtifactDomain(artifact_id=a_bot.id, domain_id=curriculum.id))
        s.add(ArtifactDomain(artifact_id=a_bot.id, domain_id=tesis.id))
        s.flush()

        # Consultas de los últimos 30 días: modelos, resultados y calificaciones variados.
        ahora = datetime.now(UTC).replace(tzinfo=None)
        modelos = {"literal": "modelo-literal-ejemplo", "razonamiento": "modelo-razonamiento-ejemplo"}
        preguntas = [
            "¿Cuántos créditos tiene el Taller de Ejemplo A?",
            "¿Qué se acordó en el Acta de ejemplo 02-2026?",
            "¿Cuáles son los requisitos de la tesis?",
            "¿Cuándo empieza el periodo de promoción?",
            "¿Cuántas horas de trabajo extraclase tiene el Seminario de Ejemplo?",
        ]
        for n in range(120):
            art = azar.choice([a_comp, a_comp, a_anal, a_bot])
            modo = "razonamiento" if art is not a_bot and azar.random() < 0.3 else "literal"
            resultado = azar.choices(["answered", "no_info", "error", "rejected_cap"], [82, 11, 4, 3])[0]
            costo =Decimal("0.003") * azar.randint(1, 3) if modo == "literal" else Decimal("0.02") * azar.randint(1, 3)
            calificacion = None
            if resultado == "answered" and azar.random() < 0.45:
                calificacion = "util" if azar.random() < 0.8 else "no_util"
            s.add(
                QueryLog(
                    id=str(uuid.uuid4()),
                    artifact_id=art.id,
                    created_at=ahora - timedelta(days=azar.random() * 30, hours=azar.random() * 8),
                    question=azar.choice(preguntas),
                    domain_ids=json.dumps([curriculum.id]),
                    mode=modo,
                    model=modelos[modo] if resultado in ("answered", "no_info") else None,
                    prompt_tokens=azar.randint(700, 2500),
                    completion_tokens=azar.randint(60, 400),
                    reasoning_tokens=azar.randint(300, 1500) if modo == "razonamiento" else None,
                    cost_usd=costo if resultado in ("answered", "no_info") else Decimal(0),
                    latency_ms=azar.randint(1800, 5200) if modo == "literal" else azar.randint(9000, 40000),
                    outcome=resultado,
                    reject_reason="Se alcanzó el tope diario de gasto" if resultado == "rejected_cap" else None,
                    sources=json.dumps([{"domain": "Currículum", "document": "Programa de curso Taller de Ejemplo A.pdf"}]),
                    rating=calificacion,
                    rating_comment="Justo lo que necesitaba." if calificacion == "util" and azar.random() < 0.2 else None,
                )
            )

        # Usuarios de la Consulta y conversaciones guardadas.
        usuario = ConsultaUser(
            id=str(uuid.uuid4()),
            username=USUARIO_CONSULTA,
            password_hash=hash_password(CLAVE_USUARIO),
            unit_id=unidades[UNIDAD_COMP].id,
            created_by="demo",
            last_login_at=ahora - timedelta(days=1),
        )
        s.add(usuario)
        otros = [("asistente.comp", UNIDAD_COMP), ("asistente.anal", UNIDAD_ANAL)]
        for nombre, unidad in otros:
            s.add(
                ConsultaUser(
                    id=str(uuid.uuid4()),
                    username=nombre,
                    password_hash=hash_password("OtraClaveDemo2026"),
                    unit_id=unidades[unidad].id,
                    created_by="demo",
                    last_login_at=ahora - timedelta(days=3),
                )
            )
        s.flush()
        for dias, titulo, pregunta, respuesta in (
            (1, "Créditos del Taller de Ejemplo A", "¿Cuántos créditos tiene el Taller de Ejemplo A?", "El Taller de Ejemplo A tiene 3 créditos."),
            (4, "Requisitos de la tesis", "¿Qué requisitos tiene la tesis?", "La guía de ejemplo pide una propuesta aprobada por el Consejo."),
        ):
            conv = Conversation(
                id=str(uuid.uuid4()),
                user_id=usuario.id,
                title=titulo,
                created_at=ahora - timedelta(days=dias),
                updated_at=ahora - timedelta(days=dias),
            )
            s.add(conv)
            s.flush()
            s.add(
                ConversationTurn(
                    id=str(uuid.uuid4()),
                    conversation_id=conv.id,
                    position=1,
                    question=pregunta,
                    answer=respuesta,
                    sources=json.dumps([{"domain": "Currículum", "document": "Programa de curso Taller de Ejemplo A.pdf"}]),
                    mode="literal",
                )
            )

        # Bot de WhatsApp (sandbox): artefacto asignado y cuota del mes.
        bot = Bot(id=str(uuid.uuid4()), name="Bot de posgrados (sandbox)", kapso_number_id="demo-phone-number-id", artifact_id=a_bot.id)
        s.add(bot)
        s.flush()
        s.add(BotMessageCount(bot_id=bot.id, month=current_month(), received=410, sent=388))
        s.commit()

        for correo, (_, alcance, _) in idp.CUENTAS.items():
            if alcance == "global":
                add_admin(s, correo, is_global=True, unit_names=[])
            elif alcance:
                add_admin(s, correo, is_global=False, unit_names=alcance)


def simular_ingesta(session_factory):
    """Sin modelo de embeddings: un documento subido pasa de en cola a procesando y a listo, con pausas, para poder grabarlo."""

    def ingest(document_id: str) -> None:
        from mia.storage.models import Document

        def cambiar(estado: str) -> None:
            with session_factory() as s:
                doc = s.get(Document, document_id)
                if doc is not None:
                    doc.status = estado
                    s.commit()

        def trabajo() -> None:
            time.sleep(5)
            cambiar("processing")
            time.sleep(12)
            cambiar("done")

        threading.Thread(target=trabajo, daemon=True).start()

    return ingest


def main() -> int:
    carpeta = Path(tempfile.mkdtemp(prefix="mia-demo-"))
    os.environ.update(
        DATABASE_URL=f"sqlite:///{carpeta}/demo.db",
        ENTRA_CLIENT_ID=idp.CLIENT_ID,
        ENTRA_TENANT_ID=idp.TENANT,
        ENTRA_REQUIRE_MFA="true",
        CORS_ORIGINS=idp.PANEL_ORIGIN,
        INGESTION_ENABLED="true",
        ADMIN_KEY=idp.CLAVE_ADMIN,
        BOT_SERVICE_KEY="clave-servicio-demo",
        BOT_CLARIFY="on",  # el bot puede preguntar a qué programa se refiere la persona
        CHAT_RETENTION_DAYS="90",
        # El modo con razonamiento figura como disponible; las respuestas las pone el grabador, nunca se llama al modelo.
        LLM_PROVIDER_RAZONAMIENTO="openrouter",
        LLM_MODEL_RAZONAMIENTO="modelo-razonamiento-ejemplo",
    )
    identidad = idp.Identidad(3600)
    import uvicorn

    from mia.api import security
    from mia.api.main import app as api
    from mia.api.routes import domains
    from mia.storage.db import SessionLocal, init_db

    init_db()
    sembrar_demo(SessionLocal)
    fuente, _ = identidad.claves_publicas()
    api.dependency_overrides[security.get_key_source] = lambda: fuente
    domains.ingest_document = simular_ingesta(SessionLocal)
    # Sin Qdrant ni modelo: la respuesta es fija, lo demás de POST /query (sesión, historial, guardado, calificación) es real.
    import respuestas_demo

    from mia.api.routes import query as ruta_query

    ruta_query.run_query = respuestas_demo.responder
    from mia.api.routes import bot_service

    bot_service.run_query = respuestas_demo.responder_bot

    # Eliminar documentos: sin Qdrant, el almacén de vectores es uno que no guarda nada (el resto del borrado es real).
    from mia.api.routes import documents as ruta_documentos

    class AlmacenDemo:
        def delete_document(self, document_id: str) -> None:
            return None

        def count_chunks(self, document_id: str) -> int:
            return 0

    ruta_documentos.get_vector_store = lambda: AlmacenDemo()

    cert, clave = idp._certificado(carpeta)
    servidor = uvicorn.Server(
        uvicorn.Config(idp.crear_idp(identidad), host="127.0.0.1", port=idp.IDP_PORT, ssl_certfile=cert, ssl_keyfile=clave, log_level="warning")
    )
    threading.Thread(target=servidor.run, daemon=True).start()
    print(f"IdP simulado: https://localhost:{idp.IDP_PORT}  |  API: http://localhost:{idp.API_PORT}  |  base {carpeta}/demo.db", flush=True)
    uvicorn.run(api, host="127.0.0.1", port=idp.API_PORT, log_level="warning", lifespan="off")
    return 0


if __name__ == "__main__":
    sys.exit(main())
