"""Pruebas de scripts/crear_servicios.py y de la configuración por cuenta de scripts/servicios.py."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

RAIZ_REPO = Path(__file__).resolve().parents[2]


def _cargar(nombre: str):
    sys.path.insert(0, str(RAIZ_REPO / "scripts"))
    try:
        spec = importlib.util.spec_from_file_location(nombre, RAIZ_REPO / "scripts" / f"{nombre}.py")
        modulo = importlib.util.module_from_spec(spec)
        sys.modules[nombre] = modulo
        spec.loader.exec_module(modulo)
        return modulo
    finally:
        sys.path.pop(0)


srv = _cargar("servicios")
crear = _cargar("crear_servicios")

URLS = {
    "MIA": "https://api.up.railway.app",
    "mia-whatsapp": "https://bot.up.railway.app",
    "mia-computacion": "https://comp.up.railway.app",
    "mia-analitica-negocios": "https://admin.up.railway.app",
    "mia-panel": "https://panel.up.railway.app",
}


def test_leer_env_ignora_comentarios_vacios_y_quita_comillas(tmp_path):
    archivo = tmp_path / ".env"
    archivo.write_text('# nota\nA=1\nB=\nC="con comillas"\nD=x=y&z=w\n\nsin_igual\n', encoding="utf-8")
    assert crear.leer_env(archivo) == {"A": "1", "C": "con comillas", "D": "x=y&z=w"}


def test_las_credenciales_se_tratan_como_secretas_y_los_ajustes_no():
    for clave in ("DATABASE_URL", "QDRANT_URL", "QDRANT_API_KEY", "ADMIN_KEY", "KAPSO_WEBHOOK_SECRET", "OPENROUTER_API_KEY"):
        assert crear.es_secreta(clave), clave
    for clave in ("QUERY_SEARCH_LIMIT", "CORS_ORIGINS", "PORT", "VITE_API_URL", "OPENROUTER_MODEL", "QDRANT_COLLECTION", "PASSWORD_MIN_CHARS"):
        assert not crear.es_secreta(clave), clave


def test_extraer_dominio_de_la_salida_de_railway():
    assert crear.extraer_dominio('{"domain": "mia-x.up.railway.app", "id": 1}') == "https://mia-x.up.railway.app"
    assert crear.extraer_dominio("Service Domain created: https://otro-prod.up.railway.app") == "https://otro-prod.up.railway.app"
    assert crear.extraer_dominio('{"domains": []}') is None


def test_secretos_solo_se_generan_si_faltan_y_se_reutilizan_los_previos():
    generados = crear.generar_secretos({"ADMIN_KEY": "a"}, {}, {"BOT_SERVICE_KEY": "previo"})
    assert set(generados) == {"BOT_SERVICE_KEY", "KAPSO_WEBHOOK_SECRET"}
    assert generados["BOT_SERVICE_KEY"] == "previo"
    assert len(generados["KAPSO_WEBHOOK_SECRET"]) >= 32
    # BOT_SERVICE_KEY puesta en cualquiera de los dos archivos no se vuelve a generar
    assert "BOT_SERVICE_KEY" not in crear.generar_secretos({}, {"BOT_SERVICE_KEY": "b"}, {})
    assert "BOT_SERVICE_KEY" not in crear.generar_secretos({"BOT_SERVICE_KEY": "b"}, {}, {})
    assert crear.generar_secretos({"ADMIN_KEY": "a", "BOT_SERVICE_KEY": "b"}, {"KAPSO_WEBHOOK_SECRET": "k"}, {}) == {}


def test_variables_api_no_copia_los_marcadores_de_la_plantilla_y_calcula_cors():
    plantilla = {"DATABASE_URL": "postgresql://usuario:clave@host.neon.tech/mia", "QDRANT_URL": "https://<cluster>.cloud.qdrant.io", "DAILY_CAP_USD": "3"}
    env_api = {"DATABASE_URL": "postgresql://real", "QDRANT_URL": "https://real.qdrant.io"}
    variables = crear.variables_api(plantilla, env_api, URLS, {"ADMIN_KEY": "gen"})
    assert variables["DATABASE_URL"] == "postgresql://real" and variables["QDRANT_URL"] == "https://real.qdrant.io"
    assert variables["DAILY_CAP_USD"] == "3" and variables["ADMIN_KEY"] == "gen"
    assert variables["CORS_ORIGINS"] == "https://comp.up.railway.app,https://admin.up.railway.app,https://panel.up.railway.app"
    solo_plantilla = crear.variables_api(plantilla, {}, URLS, {})
    assert "DATABASE_URL" not in solo_plantilla and "QDRANT_URL" not in solo_plantilla


def test_variables_del_bot_y_de_los_sitios():
    bot = crear.variables_bot({"KAPSO_API_KEY": "k"}, URLS["MIA"], "svc", {"KAPSO_WEBHOOK_SECRET": "w"})
    assert bot == {"KAPSO_API_KEY": "k", "MIA_API_URL": URLS["MIA"], "BOT_SERVICE_KEY": "svc", "KAPSO_WEBHOOK_SECRET": "w"}
    propio = crear.variables_bot({"KAPSO_WEBHOOK_SECRET": "mio"}, URLS["MIA"], "svc", {})
    assert propio["KAPSO_WEBHOOK_SECRET"] == "mio"
    assert crear.variables_sitio(URLS["MIA"]) == {"VITE_API_URL": URLS["MIA"], "PORT": "3000"}


def test_faltantes_y_aviso_de_pooler():
    assert crear.faltantes({"DATABASE_URL": "x"}, ("DATABASE_URL", "QDRANT_URL")) == ["QDRANT_URL"]
    assert crear.avisos_api({"DATABASE_URL": "postgresql://u:p@ep-x-pooler.neon.tech/db"})
    assert not crear.avisos_api({"DATABASE_URL": "postgresql://u:p@ep-x.neon.tech/db"})


def test_openrouter_model_solo_se_exige_si_algun_modo_no_tiene_modelo_propio():
    por_modo = {"LLM_PROVIDER": "openrouter", "LLM_PROVIDER_RAZONAMIENTO": "openrouter",
                "LLM_MODEL_LITERAL": "a/b", "LLM_MODEL_RAZONAMIENTO": "c/d"}
    assert crear.modos_sin_modelo(por_modo) == []
    assert crear.modos_sin_modelo({**por_modo, "LLM_MODEL_RAZONAMIENTO": ""}) == ["LLM_MODEL_RAZONAMIENTO"]
    assert crear.modos_sin_modelo({"LLM_PROVIDER": "openrouter"}) == ["LLM_MODEL_LITERAL"]
    assert crear.modos_sin_modelo({"LLM_PROVIDER": "openrouter", "OPENROUTER_MODEL": "a/b"}) == []


def test_los_secretos_no_van_por_la_linea_de_comandos(monkeypatch):
    llamadas = []

    class Falso(crear.Ejecutor):
        def correr(self, *args, entrada=None, cambia=True):
            llamadas.append((args, entrada))
            return ""

    crear.poner_variables(Falso(False), "MIA", {"PORT": "3000", "ADMIN_KEY": "s3creto", "CORS_ORIGINS": "https://a"})
    for args, _ in llamadas:
        assert "s3creto" not in " ".join(args)
    por_stdin = [(args, entrada) for args, entrada in llamadas if entrada is not None]
    assert por_stdin == [(("variable", "set", "ADMIN_KEY", "--stdin", "-s", "MIA", "--skip-deploys"), "s3creto")]
    assert all("--skip-deploys" in args for args, _ in llamadas)


def test_simular_no_ejecuta_railway_ni_escribe_archivos(tmp_path, monkeypatch, capsys):
    env_api = tmp_path / "api.env"
    env_api.write_text("DATABASE_URL=postgresql://u:p@ep-x.neon.tech/db\nQDRANT_URL=https://q.io\nQDRANT_API_KEY=k\n"
                       "OPENROUTER_API_KEY=o\nOPENROUTER_MODEL=m\n", encoding="utf-8")
    monkeypatch.setattr(crear.subprocess, "run", lambda *a, **k: pytest.fail("no debe ejecutar nada en la simulación"))
    monkeypatch.setattr(srv, "ARCHIVO_CONFIG", tmp_path / "servicios.local.json")
    monkeypatch.setattr(crear, "ARCHIVO_SECRETOS", tmp_path / ".env.railway.generado")
    monkeypatch.setattr(sys, "argv", ["crear_servicios.py", "--proyecto", "mia", "--env-api", str(env_api), "--simular"])
    assert crear.main() == 0
    salida = capsys.readouterr().out
    assert "[simulado] railway init --name mia" in salida
    assert "[simulado] railway add --service MIA" in salida and "[simulado] railway add --service mia-panel" in salida
    assert "--port 3000" in salida and "--skip-deploys" in salida
    assert not (tmp_path / "servicios.local.json").exists() and not (tmp_path / ".env.railway.generado").exists()


def test_sin_credenciales_obligatorias_falla_salvo_en_simulacion(tmp_path, monkeypatch, capsys):
    env_api = tmp_path / "api.env"
    env_api.write_text("DATABASE_URL=postgresql://u:p@h/db\n", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["crear_servicios.py", "--proyecto", "mia", "--env-api", str(env_api)])
    monkeypatch.setattr(crear.shutil, "which", lambda _: "/usr/bin/railway")
    monkeypatch.setattr(crear.subprocess, "run", lambda *a, **k: pytest.fail("no debe llegar a Railway"))
    assert crear.main() == 2
    assert "QDRANT_URL" in capsys.readouterr().err


# --- scripts/servicios.py: configuración por cuenta ---


def test_sin_archivo_de_configuracion_todo_queda_como_antes(tmp_path):
    assert srv.cargar_configuracion(tmp_path / "no_existe.json") == {}
    assert srv.aplicar_configuracion({}) == srv.SERVICIOS


def test_la_configuracion_cambia_las_direcciones_y_deja_el_resto(tmp_path):
    ruta = tmp_path / "servicios.local.json"
    ruta.write_text(json.dumps({"urls": {"MIA": "https://nueva.up.railway.app/"}, "subir_carpeta": True}), encoding="utf-8")
    config = srv.cargar_configuracion(ruta)
    catalogo = srv.aplicar_configuracion(config)
    por_nombre = {s.nombre: s for s in catalogo}
    assert por_nombre["MIA"].url == "https://nueva.up.railway.app"
    assert por_nombre["mia-panel"].url == srv.POR_NOMBRE["mia-panel"].url
    assert [s.nombre for s in srv.seleccionar(["mia-panel", "MIA"], catalogo=catalogo)] == ["MIA", "mia-panel"]
    assert config["subir_carpeta"] is True


def test_configuracion_invalida_da_un_error_claro(tmp_path):
    ruta = tmp_path / "c.json"
    ruta.write_text("{no es json", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON válido"):
        srv.cargar_configuracion(ruta)
    ruta.write_text(json.dumps({"urls": {"otro": "https://x"}}), encoding="utf-8")
    with pytest.raises(ValueError, match="desconocidos"):
        srv.cargar_configuracion(ruta)


def test_con_subir_carpeta_cada_servicio_se_sube_desde_su_carpeta():
    base = Path("/tmp/codigo")
    destinos = {s.nombre: srv.carpeta_de_subida(s, base, True) for s in srv.SERVICIOS}
    assert destinos == {
        "MIA": base,
        "mia-whatsapp": base / "whatsapp",
        "mia-computacion": base / "web/consulta",
        "mia-analitica-negocios": base / "web/consulta",
        "mia-panel": base / "web/admin",
    }
    assert all(srv.carpeta_de_subida(s, base, False) == base for s in srv.SERVICIOS)


def test_las_carpetas_de_los_servicios_existen_con_su_dockerfile():
    for servicio in srv.SERVICIOS:
        assert (RAIZ_REPO / servicio.carpeta / "Dockerfile").is_file(), servicio.nombre
