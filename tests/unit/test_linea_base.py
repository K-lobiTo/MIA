import importlib.util
import json
import os
from pathlib import Path

import pytest

RAIZ_REPO = Path(__file__).resolve().parents[2]


def _cargar(nombre: str):
    spec = importlib.util.spec_from_file_location(nombre, RAIZ_REPO / "scripts" / f"{nombre}.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


lb = _cargar("linea_base")


def _caso(**extra):
    base = {
        "id": "X1", "categoria": "mvp", "dominios": ["P / D"], "pregunta": "¿Algo?",
        "espera": "respuesta", "documentos": ["acta"],
    }
    return {**base, **extra}


def _escribir(tmp_path, casos):
    ruta = tmp_path / "casos.json"
    ruta.write_text(json.dumps(casos), encoding="utf-8")
    return ruta


def _cand(*puntajes, doc="acta-01.pdf"):
    return [
        {"posicion": i, "puntaje": p, "documento": doc if i == 1 else f"otro-{i}.pdf", "dominio": "P / D"}
        for i, p in enumerate(puntajes, start=1)
    ]


# --- Casos y entorno --------------------------------------------------------------


def test_el_script_importa():
    assert callable(lb.main)


def test_cargar_casos_valido(tmp_path):
    assert lb.cargar_casos(_escribir(tmp_path, [_caso()]))[0]["id"] == "X1"


@pytest.mark.parametrize(
    "casos, mensaje",
    [
        ([_caso(), _caso()], "id repetido"),
        ([_caso(espera="quizas")], "espera inválida"),
        ([_caso(documentos=[])], "no declara los documentos"),
        ([_caso(categoria="otra")], "categoría inválida"),
        ([_caso(dominios=[])], "faltan los dominios"),
        ([_caso(pregunta="")], "falta la pregunta"),
        ([], "al menos un caso"),
    ],
)
def test_cargar_casos_invalido(tmp_path, casos, mensaje):
    with pytest.raises(ValueError, match=mensaje):
        lb.cargar_casos(_escribir(tmp_path, casos))


def test_sin_informacion_no_exige_documentos(tmp_path):
    caso = _caso(espera="sin_informacion", documentos=[])
    assert lb.cargar_casos(_escribir(tmp_path, [caso]))


def test_cargar_env_prioridad_y_valor_con_ampersand(tmp_path, monkeypatch):
    archivo = tmp_path / "env"
    archivo.write_text(
        "# comentario\nA=nuevo\nexport B='con & signo'\nURL=postgresql://u:p@h/db?sslmode=require&x=1\n\nC=\"entre comillas\"\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("A", "viejo")
    monkeypatch.delenv("B", raising=False)
    monkeypatch.delenv("URL", raising=False)
    monkeypatch.delenv("C", raising=False)
    assert lb.cargar_env(archivo, sobrescribir=True) == 4
    assert os.environ["A"] == "nuevo"
    assert os.environ["B"] == "con & signo"
    assert os.environ["URL"].endswith("sslmode=require&x=1")
    assert os.environ["C"] == "entre comillas"


def test_cargar_env_sin_sobrescribir(tmp_path, monkeypatch):
    archivo = tmp_path / "env"
    archivo.write_text("A=archivo\nB=archivo\n", encoding="utf-8")
    monkeypatch.setenv("A", "shell")
    monkeypatch.delenv("B", raising=False)
    lb.cargar_env(archivo, sobrescribir=False)
    assert os.environ["A"] == "shell" and os.environ["B"] == "archivo"


def test_cargar_env_archivo_inexistente(tmp_path):
    assert lb.cargar_env(tmp_path / "no-existe") == 0


def test_destino_de():
    assert lb.destino_de("http://localhost:6333") == "local"
    assert lb.destino_de("http://127.0.0.1:8000/x") == "local"
    assert lb.destino_de("https://abc.cloud.qdrant.io:6333") == "produccion"
    assert lb.destino_de("https://mia-main.up.railway.app") == "produccion"


def test_guardar_y_leer_corrida(tmp_path, monkeypatch):
    monkeypatch.setattr(lb, "SALIDA", tmp_path)
    contexto = lb.contexto_corrida("base-x", "local")
    carpeta = tmp_path / ("20260101-101010-base-x")
    lb.guardar_json(carpeta, "puntajes.json", {"contexto": contexto})
    corrida = lb.leer_corrida("base-x", base=tmp_path)
    assert corrida["puntajes"]["contexto"]["etiqueta"] == "base-x"
    assert corrida["respuestas"] is None
    with pytest.raises(FileNotFoundError):
        lb.leer_corrida("otra", base=tmp_path)


def test_leer_corrida_une_puntajes_y_respuestas_de_carpetas_distintas(tmp_path):
    lb.guardar_json(tmp_path / "20260101-101010-base", "puntajes.json", {"contexto": {}, "n": 1})
    lb.guardar_json(tmp_path / "20260101-111111-base", "respuestas.json", {"n": 2})
    lb.guardar_json(tmp_path / "20260101-121212-base", "puntajes.json", {"contexto": {}, "n": 3})
    corrida = lb.leer_corrida("base", base=tmp_path)
    assert corrida["puntajes"]["n"] == 3 and corrida["respuestas"]["n"] == 2


def test_tmp_esta_ignorado_por_git():
    gitignore = (RAIZ_REPO / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "tmp/" in gitignore


# --- Puntajes ---------------------------------------------------------------------


def test_resultado_por_modo_respeta_limite_y_borde():
    cand = _cand(0.70, 0.79, 0.82)  # el que alcanza está en la posición 3
    assert lb.resultado_por_modo(cand, 2, 0.82)["resultado"] == "sin_informacion"
    assert lb.resultado_por_modo(cand, 3, 0.82)["resultado"] == "responde"  # puntaje == umbral pasa
    assert lb.resultado_por_modo(cand, 3, 0.82)["pasan"] == 1
    assert lb.resultado_por_modo([], 8, 0.8)["mejor_puntaje"] is None


def test_posicion_esperados():
    cand = [
        {"posicion": 1, "puntaje": 0.9, "documento": "Acta 01.pdf", "dominio": "d"},
        {"posicion": 2, "puntaje": 0.8, "documento": "Programa.docx", "dominio": "d"},
        {"posicion": 3, "puntaje": 0.7, "documento": "Programa.docx", "dominio": "d"},
    ]
    r = lb.posicion_esperados(cand, ["programa", "inexistente"])
    assert r[0] == {"fragmento": "programa", "posicion": 2, "puntaje": 0.8}
    assert r[1] == {"fragmento": "inexistente", "posicion": None, "puntaje": None}


def _med(caso_id, espera, puntajes, doc_puntaje=None, grupo=None, variante="completa"):
    cand = _cand(*puntajes)
    esperados = [{"fragmento": "x", "posicion": 1, "puntaje": doc_puntaje}] if doc_puntaje is not None else []
    if espera == "respuesta" and doc_puntaje is None:
        esperados = [{"fragmento": "x", "posicion": None, "puntaje": None}]
    return {
        "caso_id": caso_id, "variante": variante, "categoria": "mvp", "grupo": grupo, "espera": espera,
        "candidatos": cand, "por_modo": {}, "esperados": esperados,
    }


def test_barrido_umbrales():
    mediciones = [_med("A", "respuesta", [0.81]), _med("B", "sin_informacion", [0.78])]
    barrido = lb.barrido_umbrales(mediciones, 0.82, {"literal": 8, "razonamiento": 16})
    filas = {f["umbral"]: f for f in barrido["literal"]}
    assert filas[0.80]["pasan_a_responder"] == ["A"]  # bajar a 0.80 hace que A responda
    assert filas[0.78]["pasan_a_responder"] == ["A", "B"]
    assert filas[0.85]["pasan_a_sin_info"] == []  # A y B ya eran "sin información" con 0.82
    assert filas[0.82]["pasan_a_responder"] == []
    otro = lb.barrido_umbrales([_med("C", "respuesta", [0.90])], 0.82, {"literal": 8})
    assert {f["umbral"]: f for f in otro["literal"]}[0.90]["pasan_a_sin_info"] == []
    assert {f["umbral"]: f for f in lb.barrido_umbrales([_med("C", "respuesta", [0.85])], 0.82, {"literal": 8})["literal"]}[0.86]["pasan_a_sin_info"] == ["C"]


def test_ventana_separable_y_no_separable():
    separable = [_med("A", "respuesta", [0.9], 0.9), _med("N", "sin_informacion", [0.7])]
    v = lb.ventana_separacion(separable)
    assert v["separables"] and v["rango"] == [0.7, 0.9]
    mezclado = [_med("A", "respuesta", [0.75], 0.75), _med("N", "sin_informacion", [0.78])]
    assert not lb.ventana_separacion(mezclado)["separables"]


def test_ventana_incluye_aislamiento_y_lo_separa():
    meds = [
        _med("A", "respuesta", [0.9], 0.9),
        _med("N", "sin_informacion", [0.6]),
        _med("I1", "sin_informacion", [0.85], grupo="I"),
    ]
    v = lb.ventana_separacion(meds)
    assert v["max_sin_info"] == 0.85 and v["max_sin_info_caso"] == "I1"
    assert v["max_sin_info_sin_aislamiento"] == 0.6


def test_ventana_lista_ausentes():
    v = lb.ventana_separacion([_med("A", "respuesta", [0.5]), _med("N", "sin_informacion", [0.4])])
    assert v["ausentes"] == ["A"] and v["min_respuesta"] is None and not v["separables"]


def test_parejas():
    meds = [_med("S", "respuesta", [0.70]), _med("S", "respuesta", [0.85], variante="corta"), _med("Z", "respuesta", [0.9])]
    filas = lb.parejas(meds, 0.82)
    assert len(filas) == 1
    assert filas[0]["completa"]["distancia_umbral"] == -0.12
    assert filas[0]["corta"]["distancia_umbral"] == 0.03


# --- Respuestas -------------------------------------------------------------------


def _body(answer="Respuesta.", docs=("Acta 01.pdf",), no_info=False):
    return {"id": "q1", "answer": answer, "no_info": no_info, "latency_ms": 10,
            "sources": [{"domain": "d", "document": d, "excerpt": "TEXTO"} for d in docs]}


def test_evaluar_respuesta_correcta_y_sobrantes():
    r = lb.evaluar_respuesta(_caso(documentos=["acta 01"]), 200, _body(docs=("Acta 01.pdf", "Otra.pdf")))
    assert r["resultado"] == "respondio" and r["correcto"]
    assert r["fuentes_mostradas"] == 2 and r["fuentes_esperadas_halladas"] == 1 and r["fuentes_sobrantes"] == 1


def test_evaluar_respuesta_no_guarda_texto():
    r = lb.evaluar_respuesta(_caso(), 200, _body(answer="SECRETO", docs=("Acta.pdf",)))
    assert "SECRETO" not in json.dumps(r) and "TEXTO" not in json.dumps(r)


def test_evaluar_respuesta_documento_esperado_ausente():
    r = lb.evaluar_respuesta(_caso(documentos=["programa"]), 200, _body(docs=("Acta.pdf",)))
    assert not r["correcto"] and r["fuentes_sobrantes"] == 1


def test_evaluar_respuesta_contiene():
    caso = _caso(contiene="14")
    assert lb.evaluar_respuesta(caso, 200, _body(answer="Son 14 horas", docs=("acta.pdf",)))["contiene_ok"] is True
    r = lb.evaluar_respuesta(caso, 200, _body(answer="Son 10", docs=("acta.pdf",)))
    assert r["contiene_ok"] is False and not r["correcto"]


def test_evaluar_sin_informacion():
    caso = _caso(espera="sin_informacion", documentos=[])
    ok = lb.evaluar_respuesta(caso, 200, _body(answer=lb.NO_INFO_PREFIX + " ...", docs=(), no_info=True))
    assert ok["resultado"] == "sin_informacion" and ok["correcto"]
    mal = lb.evaluar_respuesta(caso, 200, _body(docs=("Acta.pdf",)))
    assert not mal["correcto"] and mal["fuentes_sobrantes"] == 1
    # Esperaba respuesta y dijo "sin información"
    r = lb.evaluar_respuesta(_caso(), 200, _body(answer=lb.NO_INFO_PREFIX, docs=(), no_info=True))
    assert r["resultado"] == "sin_informacion" and not r["correcto"]


def test_evaluar_no_concluyente():
    r = lb.evaluar_respuesta(_caso(), 502, {})
    assert r["resultado"] == "no_concluyente" and not r["correcto"]


def test_percentil():
    assert lb.percentil([], 50) is None
    assert lb.percentil([1, 2, 3, 4], 50) == 2
    assert lb.percentil([1, 2, 3, 4], 95) == 4
    assert lb.percentil([5], 95) == 5


def test_resumen_respuestas_con_costos_nulos():
    base = {"modo": "literal", "variante": "completa", "latencia_cliente_ms": 1000, "fuentes_sobrantes": 1}
    resultados = [
        {**base, "caso_id": "A", "resultado": "respondio", "correcto": True, "costo_usd": 0.01},
        {**base, "caso_id": "B", "resultado": "sin_informacion", "correcto": False, "costo_usd": None},
        {**base, "caso_id": "C", "resultado": "no_concluyente", "correcto": False, "costo_usd": None, "latencia_cliente_ms": None},
    ]
    r = lb.resumen_respuestas(resultados)["literal"]
    assert r["correctos"] == ["A"] and r["fallidos"] == ["B"] and r["no_concluyentes"] == ["C"]
    assert r["costo_medio_usd"] == 0.01 and r["costo_medio_sin_info_usd"] is None and r["gasto_total_usd"] == 0.01


def test_correr_respuestas_se_detiene_en_el_tope():
    casos = [_caso(id=f"C{i}") for i in range(5)]
    llamadas = []

    def consultar(caso, variante, modo):
        llamadas.append(caso["id"])
        return 200, _body(docs=("acta.pdf",)), 100

    corrida = lb.correr_respuestas(casos, ["literal"], consultar, lambda _id: {"cost_usd": 0.02}, 0.05)
    # 0.02 + 0.02 = 0.04 < 0.05, una tercera lleva a 0.06 >= 0.05 y para antes de la cuarta
    assert len(corrida["resultados"]) == 3 and corrida["parcial"] and corrida["motivo_parada"] == "tope_usd"
    assert corrida["gasto_total_usd"] == pytest.approx(0.06)


def test_correr_respuestas_se_detiene_ante_429():
    corrida = lb.correr_respuestas(
        [_caso(id="A"), _caso(id="B")], ["literal"], lambda c, v, m: (429, {}, 5), lambda _id: None, 1.0
    )
    assert corrida["resultados"] == [] and corrida["motivo_parada"] == "tope_diario_del_artefacto"


def test_correr_respuestas_incluye_variante_corta_y_ambos_modos():
    caso = _caso(variante_corta="corta")
    vistos = []

    def consultar(c, variante, modo):
        vistos.append((variante, modo))
        return 200, _body(docs=("acta.pdf",)), 1

    lb.correr_respuestas([caso], ["literal", "razonamiento"], consultar, lambda _id: {"cost_usd": 0.0}, 1.0)
    assert sorted(vistos) == [("completa", "literal"), ("completa", "razonamiento"), ("corta", "literal"), ("corta", "razonamiento")]


# --- Comparación e informe --------------------------------------------------------


def _corrida(mejor=0.9, fragmentos=10, resultado="responde"):
    cand = _cand(mejor)
    return {
        "puntajes": {
            "contexto": {"fragmentos_por_dominio": {"P / D": fragmentos}},
            "mediciones": [{
                "caso_id": "A", "variante": "completa", "candidatos": cand,
                "por_modo": {"literal": {"resultado": resultado}, "razonamiento": {"resultado": resultado}},
            }],
        },
        "respuestas": None,
    }


def test_comparar_sin_diferencias_y_tolerancia():
    assert lb.comparar(_corrida(), _corrida())["cambios"] == []
    assert lb.comparar(_corrida(0.9), _corrida(0.9005))["cambios"] == []  # menor a 0,001: no se reporta


def test_comparar_detecta_cambios():
    r = lb.comparar(_corrida(0.9), _corrida(0.8, resultado="sin_informacion"))
    assert any("mejor puntaje" in c for c in r["cambios"]) and any("resultado" in c for c in r["cambios"])


def test_comparar_avisa_datos_distintos():
    assert lb.comparar(_corrida(fragmentos=10), _corrida(fragmentos=11))["datos_distintos"]


def test_informe_sin_guion_largo_ni_claves(tmp_path):
    mediciones = [_med("A", "respuesta", [0.9], 0.9), _med("N", "sin_informacion", [0.6])]
    for m in mediciones:
        m["por_modo"] = {k: lb.resultado_por_modo(m["candidatos"], 8, 0.82) for k in lb.MODOS}
    contexto = {
        "etiqueta": "t", "fecha": "2026-10-15T10:00:00", "commit": "abc1234567", "cambios_sin_confirmar": False,
        "destino": "produccion", "umbral": 0.82, "limite_literal": 8, "limite_razonamiento": 16,
        "candidatos_pedidos": 50, "proveedor_embeddings": "local", "dimension": 384,
        "fragmentos_por_dominio": {"P / D": 10}, "casos_omitidos": [],
    }
    limites = {"literal": 8, "razonamiento": 16}
    corrida = {"puntajes": {"contexto": contexto, "mediciones": mediciones,
                            "resumen": lb.resumen_puntajes(mediciones, 0.82, limites)}, "respuestas": None}
    texto = lb.generar_informe(corrida)
    assert chr(0x2014) not in texto
    assert "Ventana de separación" in texto and "Barrido de umbrales" in texto
    with pytest.raises(ValueError):
        lb.generar_informe({"puntajes": None, "respuestas": None})


# --- Solo lectura -----------------------------------------------------------------


def test_cliente_solo_lectura_bloquea_escrituras():
    class Falso:
        def query_points(self):
            return "ok"

        def upsert(self):
            raise AssertionError("no debería llamarse")

    cliente = lb.ClienteSoloLectura(Falso())
    assert cliente.query_points() == "ok"
    with pytest.raises(PermissionError):
        getattr(cliente, "upsert")  # noqa: B009
    with pytest.raises(PermissionError):
        getattr(cliente, "delete_collection")  # noqa: B009


# --- Archivo real de casos ----------------------------------------------------------


def _cargar_bateria():
    return _cargar("pruebas_mvp")


def test_archivo_de_casos_real():
    casos = lb.cargar_casos()
    por_id = {c["id"]: c for c in casos}
    # Toda la batería del MVP está con la misma pregunta, dominios y resultado esperado (FR-002, SC-001).
    for original in _cargar_bateria().CASOS:
        caso = por_id[original.id]
        assert caso["pregunta"] == original.pregunta
        assert caso["dominios"] == original.dominios
        assert caso["espera"] == original.espera
        assert caso["categoria"] == "mvp"


def test_archivo_de_casos_cubre_las_categorias():
    casos = lb.cargar_casos()
    for categoria in ("indirecta", "sigla", "sin_respuesta"):
        assert sum(1 for c in casos if c["categoria"] == categoria) >= 3
    con_variante = [c for c in casos if c["categoria"] == "seccion_2_2" and c.get("variante_corta")]
    assert len(con_variante) >= 2


# --- Convergencia: solo lectura de la base, códigos de salida y paradas -------------


def test_sesion_solo_lectura_en_sqlite(tmp_path):
    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import OperationalError

    engine = create_engine(f"sqlite:///{tmp_path}/lectura.db")
    with engine.begin() as conexion:
        conexion.execute(text("CREATE TABLE t (x INTEGER)"))
        conexion.execute(text("INSERT INTO t VALUES (1)"))
    sesion = lb.sesion_solo_lectura(engine)
    try:
        assert sesion.execute(text("SELECT x FROM t")).scalar() == 1
        with pytest.raises(OperationalError):
            sesion.execute(text("INSERT INTO t VALUES (2)"))
        sesion.rollback()
    finally:
        sesion.get_bind().close()
        engine.dispose()


def test_exigir_casos():
    lb.exigir_casos([{"id": "A"}], [])
    with pytest.raises(lb.ErrorMedicion, match="--solo"):
        lb.exigir_casos([], [])
    with pytest.raises(lb.ErrorMedicion, match="X1 \\(sin acceso\\)"):
        lb.exigir_casos([], [{"id": "X1", "motivo": "sin acceso"}])


def test_main_devuelve_2_cuando_no_puede_medir(monkeypatch, capsys):
    # Sin tope de gasto
    assert lb.main(["respuestas", "--etiqueta", "t", "--url", "http://x", "--clave", "k"]) == 2
    assert "--tope-usd" in capsys.readouterr().err
    # Archivo de entorno ilegible: no se llega a abrir nada
    assert lb.main(["puntajes", "--etiqueta", "t", "--env-file", "/no/existe/.env"]) == 2
    assert "archivo de entorno" in capsys.readouterr().err


def test_correr_respuestas_se_detiene_ante_401_y_403():
    for status in (401, 403):
        corrida = lb.correr_respuestas(
            [_caso(id="A"), _caso(id="B")], ["literal"], lambda c, v, m, st=status: (st, {}, 5), lambda _id: None, 1.0
        )
        assert corrida["resultados"] == [] and corrida["parcial"]
        assert corrida["motivo_parada"] == "clave_invalida_o_artefacto_desactivado"


def test_parametros_de_puntajes(monkeypatch):
    contexto = {"umbral": 0.82, "limite_literal": 8, "limite_razonamiento": 16,
                "fragmentos_por_dominio": {"P / D": 10}, "fecha": "2026-10-15", "otro": "no se copia"}
    monkeypatch.setattr(lb, "leer_corrida", lambda etiqueta: {"puntajes": {"contexto": contexto}, "respuestas": None})
    parametros = lb.parametros_de_puntajes("base")
    assert parametros["umbral"] == 0.82 and parametros["fragmentos_por_dominio"] == {"P / D": 10}
    assert "otro" not in parametros

    def sin_corrida(etiqueta):
        raise FileNotFoundError(etiqueta)

    monkeypatch.setattr(lb, "leer_corrida", sin_corrida)
    assert lb.parametros_de_puntajes("base") is None


def test_informe_muestra_los_casos_omitidos_de_respuestas():
    mediciones = [_med("A", "respuesta", [0.9], 0.9)]
    for m in mediciones:
        m["por_modo"] = {k: lb.resultado_por_modo(m["candidatos"], 8, 0.82) for k in lb.MODOS}
    contexto = {
        "etiqueta": "t", "fecha": "2026-10-15T10:00:00", "commit": "abc1234567", "cambios_sin_confirmar": False,
        "destino": "produccion", "umbral": 0.82, "limite_literal": 8, "limite_razonamiento": 16,
        "candidatos_pedidos": 50, "proveedor_embeddings": "local", "dimension": 384,
        "fragmentos_por_dominio": {"P / D": 10}, "casos_omitidos": [],
    }
    resultados = [{
        "caso_id": "A", "variante": "completa", "modo": "literal", "resultado": "respondio", "correcto": True,
        "fuentes_mostradas": 1, "fuentes_sobrantes": 0, "latencia_cliente_ms": 1000, "costo_usd": 0.001,
    }]
    respuestas = {
        "contexto": {"fecha": "2026-10-15T10:05:00", "destino": "produccion", "artefacto": "Prueba", "modos": ["literal"],
                     "tope_usd": 0.2, "casos_omitidos": [{"id": "N1", "motivo": "el artefacto no puede consultar"}]},
        "resultados": resultados, "parcial": False, "motivo_parada": None, "gasto_total_usd": 0.001,
        "resumen": lb.resumen_respuestas(resultados),
    }
    corrida = {
        "puntajes": {"contexto": contexto, "mediciones": mediciones,
                     "resumen": lb.resumen_puntajes(mediciones, 0.82, {"literal": 8, "razonamiento": 16})},
        "respuestas": respuestas,
    }
    texto = lb.generar_informe(corrida)
    assert "Casos omitidos en esta corrida: N1 (el artefacto no puede consultar)" in texto
    assert chr(0x2014) not in texto


def test_informe_conserva_la_lectura_al_regenerar(tmp_path, monkeypatch):
    destino = tmp_path / "informe.md"
    destino.write_text("# viejo\n\n## Lectura\n\nTexto escrito a mano.\n", encoding="utf-8")
    monkeypatch.setattr(lb, "leer_corrida", lambda etiqueta: {"puntajes": {"x": 1}, "respuestas": None})
    monkeypatch.setattr(lb, "generar_informe", lambda corrida: "# nuevo\n")
    assert lb.main(["informe", "t", "--salida", str(destino)]) == 0
    contenido = destino.read_text(encoding="utf-8")
    assert contenido.startswith("# nuevo") and "Texto escrito a mano." in contenido and "viejo" not in contenido


# --- Feature 006: regla de seguridad y medianas de razón -----------------------------------


def test_correr_respuestas_registra_la_regla_de_seguridad():
    notas = {
        "q-con": "Fuentes: sin citas utilizables, se mostraron todas",
        "q-sin": None,
    }

    def consultar(caso, variante, modo):
        cuerpo = _body(docs=("acta.pdf",))
        cuerpo["id"] = "q-con" if caso["id"] == "A" else "q-sin"
        return 200, cuerpo, 100

    def costo(consulta_id):
        return {"cost_usd": 0.01, "reject_reason": notas[consulta_id]}

    corrida = lb.correr_respuestas([_caso(id="A"), _caso(id="B")], ["literal"], consultar, costo, 1.0)
    por_caso = {r["caso_id"]: r["regla_de_seguridad"] for r in corrida["resultados"]}
    assert por_caso == {"A": True, "B": False}


def test_regla_de_seguridad_nula_si_no_hay_detalle_de_uso():
    corrida = lb.correr_respuestas(
        [_caso(id="A")], ["literal"], lambda c, v, m: (200, _body(docs=("acta.pdf",)), 1), lambda _id: None, 1.0
    )
    assert corrida["resultados"][0]["regla_de_seguridad"] is None


def test_resumen_respuestas_cuenta_la_regla_de_seguridad():
    base = {"modo": "literal", "variante": "completa", "latencia_cliente_ms": 1000, "fuentes_sobrantes": 0,
            "correcto": True, "costo_usd": 0.01}
    resultados = [
        {**base, "caso_id": "A", "resultado": "respondio", "regla_de_seguridad": True},
        {**base, "caso_id": "B", "resultado": "respondio", "regla_de_seguridad": False},
        {**base, "caso_id": "C", "resultado": "respondio", "regla_de_seguridad": False},
        {**base, "caso_id": "D", "resultado": "respondio", "regla_de_seguridad": False},
        {**base, "caso_id": "N", "resultado": "sin_informacion", "regla_de_seguridad": False},
    ]
    r = lb.resumen_respuestas(resultados)["literal"]
    assert r["regla_de_seguridad_aplicada"] == 1
    assert r["proporcion_regla_de_seguridad"] == pytest.approx(0.25)  # 1 de 4 respuestas con contenido


def test_resumen_respuestas_sin_dato_de_regla_de_seguridad_no_falla():
    base = {"modo": "literal", "variante": "completa", "latencia_cliente_ms": 1000, "fuentes_sobrantes": 0,
            "correcto": True, "costo_usd": 0.01, "resultado": "respondio"}
    r = lb.resumen_respuestas([{**base, "caso_id": "A"}])["literal"]  # corridas anteriores a la 006
    assert r["regla_de_seguridad_aplicada"] == 0 and r["proporcion_regla_de_seguridad"] is None


def _resp(caso, modo, costo, latencia, sobrantes=0, regla=None, mostradas=1):
    return {
        "caso_id": caso, "variante": "completa", "modo": modo, "resultado": "respondio", "correcto": True,
        "fuentes_mostradas": mostradas, "fuentes_sobrantes": sobrantes, "costo_usd": costo,
        "latencia_cliente_ms": latencia, "regla_de_seguridad": regla,
    }


def test_comparar_medianas_de_razon_de_costo_y_latencia():
    a = {"puntajes": None, "respuestas": {"resultados": [
        _resp("A", "literal", 0.010, 1000), _resp("B", "literal", 0.020, 2000), _resp("C", "literal", 0.040, 4000),
        _resp("D", "literal", None, 500),
    ]}}
    b = {"puntajes": None, "respuestas": {"resultados": [
        _resp("A", "literal", 0.011, 1100), _resp("B", "literal", 0.022, 2400), _resp("C", "literal", 0.100, 4400),
        _resp("D", "literal", 0.5, 500),
    ]}}
    resultado = lb.comparar(a, b)
    literal = resultado["medianas"]["literal"]
    assert literal["casos"] == 3  # D se descarta: sin costo en una de las corridas
    assert literal["razon_costo"] == pytest.approx(1.1)  # razones 1.1, 1.1 y 2.5: la mediana ignora el extremo
    assert literal["razon_latencia"] == pytest.approx(1.1)  # razones 1.1, 1.2 y 1.1


def test_comparar_informa_cambios_de_la_regla_de_seguridad_y_de_fuentes():
    a = {"puntajes": None, "respuestas": {"resultados": [_resp("A", "literal", 0.01, 1000, sobrantes=3, mostradas=4)]}}
    b = {"puntajes": None, "respuestas": {"resultados": [_resp("A", "literal", 0.01, 1000, sobrantes=0, regla=True)]}}
    cambios = lb.comparar(a, b)["cambios"]
    assert any("regla_de_seguridad" in c for c in cambios)
    assert any("fuentes_sobrantes 3 -> 0" in c for c in cambios)


def test_comparar_sin_respuestas_no_calcula_medianas():
    assert lb.comparar(_corrida(), _corrida())["medianas"] == {}


def test_comparar_corridas_viejas_sin_regla_de_seguridad_no_falla():
    a = {"puntajes": None, "respuestas": {"resultados": [_resp("A", "literal", 0.01, 1000)]}}
    del a["respuestas"]["resultados"][0]["regla_de_seguridad"]
    assert lb.comparar(a, a)["cambios"] == []
