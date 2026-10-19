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
    a = {"puntajes": None, "respuestas": {"resultados": [_resp("A", "literal", 0.01, 1000, sobrantes=3, mostradas=4, regla=False)]}}
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


def test_comparar_ignora_la_regla_de_seguridad_desconocida_en_una_corrida():
    a = {"puntajes": None, "respuestas": {"resultados": [_resp("A", "literal", 0.01, 1000, regla=None)]}}
    b = {"puntajes": None, "respuestas": {"resultados": [_resp("A", "literal", 0.01, 1000, regla=False)]}}
    assert lb.comparar(a, b)["cambios"] == []


# --- Feature 007: listas largas, reintentos y cortes ----------------------------------------------


def test_la_categoria_lista_larga_exige_contiene(tmp_path):
    ok = _caso(id="L1", categoria="lista_larga", contiene="Control de calidad")
    assert lb.cargar_casos(_escribir(tmp_path, [ok]))[0]["categoria"] == "lista_larga"
    sin = _caso(id="L2", categoria="lista_larga")
    with pytest.raises(ValueError, match="contiene"):
        lb.cargar_casos(_escribir(tmp_path, [sin]))


@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("Termina con punto.", False),
        ("Termina con pregunta?", False),
        ("Termina entre paréntesis (ver arriba)", False),
        ("- Último ítem de una lista **Control de calidad**", False),  # cierra con negritas
        ("Dos puntos:", False),
        ("Cortada a la mi", True),
        ("(valor de beca de", True),
        ("Lista\n10. Experimentos y Control de Calidad", True),
    ],
)
def test_termina_sin_puntuacion(texto, esperado):
    r = lb.evaluar_respuesta(_caso(documentos=["acta"]), 200, _body(answer=texto))
    assert r["termina_sin_puntuacion"] is esperado
    assert texto not in json.dumps(r)  # el texto no se conserva


def test_aviso_de_corte_y_sin_informacion():
    con = lb.evaluar_respuesta(_caso(), 200, _body(answer="Texto\n\nAviso: la respuesta pudo quedar incompleta."))
    assert con["aviso_de_corte"] is True and con["termina_sin_puntuacion"] is False
    sin = lb.evaluar_respuesta(_caso(), 200, _body(answer="Texto completo."))
    assert sin["aviso_de_corte"] is False
    no_info = lb.evaluar_respuesta(
        _caso(espera="sin_informacion", documentos=[]), 200, _body(answer=lb.NO_INFO_PREFIX, docs=(), no_info=True)
    )
    assert no_info["termina_sin_puntuacion"] is False and no_info["aviso_de_corte"] is False
    assert lb.evaluar_respuesta(_caso(), 502, {})["termina_sin_puntuacion"] is None


def test_correr_respuestas_registra_el_reintento_y_el_aviso_desde_el_registro_de_uso():
    notas = {
        "q-reintento": "Respuesta cortada: se reintentó",
        "q-aviso": "Respuesta cortada: se entregó con aviso",
        "q-ninguna": None,
    }
    ids = {"A": "q-reintento", "B": "q-aviso", "C": "q-ninguna"}

    def consultar(caso, variante, modo):
        cuerpo = _body(answer="Texto completo.", docs=("acta.pdf",))
        cuerpo["id"] = ids[caso["id"]]
        return 200, cuerpo, 100

    corrida = lb.correr_respuestas(
        [_caso(id="A"), _caso(id="B"), _caso(id="C")], ["literal"], consultar,
        lambda consulta_id: {"cost_usd": 0.01, "reject_reason": notas[consulta_id]}, 1.0,
    )
    por_caso = {r["caso_id"]: (r["reintento"], r["aviso_de_corte"]) for r in corrida["resultados"]}
    assert por_caso == {"A": (True, False), "B": (False, True), "C": (False, False)}


def test_reintento_nulo_si_no_hay_detalle_de_uso():
    corrida = lb.correr_respuestas(
        [_caso(id="A")], ["literal"], lambda c, v, m: (200, _body(docs=("acta.pdf",)), 1), lambda _id: None, 1.0
    )
    assert corrida["resultados"][0]["reintento"] is None


def test_resumen_respuestas_suma_reintentos_avisos_y_terminaciones():
    base = {"modo": "literal", "variante": "completa", "latencia_cliente_ms": 1000, "fuentes_sobrantes": 0,
            "correcto": True, "costo_usd": 0.01, "resultado": "respondio", "regla_de_seguridad": False}
    resultados = [
        {**base, "caso_id": "A", "reintento": True, "aviso_de_corte": False, "termina_sin_puntuacion": False},
        {**base, "caso_id": "B", "reintento": False, "aviso_de_corte": True, "termina_sin_puntuacion": False},
        {**base, "caso_id": "C", "reintento": False, "aviso_de_corte": False, "termina_sin_puntuacion": True},
        {**base, "caso_id": "D", "reintento": False, "aviso_de_corte": False, "termina_sin_puntuacion": False},
    ]
    r = lb.resumen_respuestas(resultados)["literal"]
    assert (r["reintentos"], r["avisos_de_corte"], r["terminan_sin_puntuacion"]) == (1, 1, 1)
    assert r["proporcion_reintentos"] == pytest.approx(0.25)
    assert r["proporcion_terminan_sin_puntuacion"] == pytest.approx(0.25)


def test_resumen_de_corridas_anteriores_a_la_007_no_falla():
    base = {"modo": "literal", "variante": "completa", "latencia_cliente_ms": 1000, "fuentes_sobrantes": 0,
            "correcto": True, "costo_usd": 0.01, "resultado": "respondio"}
    r = lb.resumen_respuestas([{**base, "caso_id": "A"}])["literal"]
    assert r["reintentos"] == 0 and r["proporcion_reintentos"] is None and r["terminan_sin_puntuacion"] == 0


def test_comparar_informa_cambios_de_reintento_y_aviso_e_ignora_los_desconocidos():
    def resp(**extra):
        return {"puntajes": None, "respuestas": {"resultados": [_resp("A", "literal", 0.01, 1000) | extra]}}

    cambios = lb.comparar(resp(reintento=False, aviso_de_corte=False), resp(reintento=True, aviso_de_corte=True))["cambios"]
    assert any("reintento False -> True" in c for c in cambios) and any("aviso_de_corte" in c for c in cambios)
    assert lb.comparar(resp(), resp(reintento=True))["cambios"] == []  # una corrida vieja no trae el dato


def test_el_informe_muestra_reintentos_avisos_y_terminaciones():
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
        "reintento": True, "aviso_de_corte": False, "termina_sin_puntuacion": False,
    }]
    corrida = {
        "puntajes": {"contexto": contexto, "mediciones": mediciones,
                     "resumen": lb.resumen_puntajes(mediciones, 0.82, {"literal": 8, "razonamiento": 16})},
        "respuestas": {"contexto": {"fecha": "2026-10-16", "destino": "produccion", "artefacto": "P", "modos": ["literal"],
                                    "tope_usd": 0.2, "casos_omitidos": []},
                       "resultados": resultados, "parcial": False, "motivo_parada": None, "gasto_total_usd": 0.001,
                       "resumen": lb.resumen_respuestas(resultados)},
    }
    texto = lb.generar_informe(corrida)
    assert "Reintentos" in texto and "avisos de posible corte" in texto and "sin puntuación" in texto
    assert chr(0x2014) not in texto


def test_el_archivo_de_casos_trae_las_listas_largas_con_su_ultimo_item():
    listas = [c for c in lb.cargar_casos() if c["categoria"] == "lista_larga"]
    assert len(listas) >= 8
    assert all(c["contiene"] for c in listas)
    assert {"MC6104", "MC8840", "MC8850", "MC8803", "MC7201", "MC6004"} <= {c["documentos"][0] for c in listas}


# --- Feature 008: pregunta limpia ------------------------------------------------------------------


def test_cargar_casos_acepta_envoltura_y_sin_pregunta_limpia(tmp_path):
    casos = lb.cargar_casos(_escribir(tmp_path, [_caso(categoria="envoltura", sin_pregunta_limpia=True)]))
    assert casos[0]["sin_pregunta_limpia"] is True


def test_cargar_casos_rechaza_un_sin_pregunta_limpia_que_no_es_booleano(tmp_path):
    with pytest.raises(ValueError, match="sin_pregunta_limpia"):
        lb.cargar_casos(_escribir(tmp_path, [_caso(sin_pregunta_limpia="si")]))


def test_variante_limpia_se_calcula_con_clean_question():
    assert lb.variante_limpia(_caso(pregunta="¿Quién es Natalia Soto Solís?")) == "Natalia Soto Solís"


def test_variante_limpia_es_nula_si_no_aplica_o_coincide_con_la_corta():
    assert lb.variante_limpia(_caso(pregunta="¿Cuántos créditos tiene el curso?")) is None
    caso = _caso(pregunta="¿Quién es Natalia Soto Solís?", variante_corta="Natalia Soto Solís")
    assert lb.variante_limpia(caso) is None
    caso = _caso(pregunta="¿Quién es Natalia Soto Solís?", variante_corta="Natalia Soto")
    assert lb.variante_limpia(caso) == "Natalia Soto Solís"


def test_correr_respuestas_registra_la_pregunta_limpia():
    notas = {
        "q-ayudo": "Pregunta limpia: «Natalia» (con resultados)",
        "q-no-ayudo": "Pregunta limpia: «Zacarías» (sin resultados); Respuesta cortada: se reintentó",
        "q-sin": None,
    }

    def consultar(caso, variante, modo):
        cuerpo = _body(docs=("acta.pdf",))
        cuerpo["id"] = {"A": "q-ayudo", "B": "q-no-ayudo"}.get(caso["id"], "q-sin")
        return 200, cuerpo, 100

    def costo(consulta_id):
        return {"cost_usd": 0.01, "reject_reason": notas[consulta_id]}

    corrida = lb.correr_respuestas([_caso(id="A"), _caso(id="B"), _caso(id="C")], ["literal"], consultar, costo, 1.0)
    por_caso = {r["caso_id"]: (r["pregunta_limpia"], r["pregunta_limpia_ayudo"]) for r in corrida["resultados"]}
    assert por_caso == {"A": (True, True), "B": (True, False), "C": (False, False)}


def test_pregunta_limpia_nula_si_no_hay_detalle_de_uso():
    corrida = lb.correr_respuestas(
        [_caso()], ["literal"], lambda c, v, m: (200, _body(docs=("acta.pdf",)), 1), lambda _id: None, 1.0
    )
    fila = corrida["resultados"][0]
    assert fila["pregunta_limpia"] is None and fila["pregunta_limpia_ayudo"] is None


def test_resumen_respuestas_cuenta_los_segundos_intentos_y_los_negativos_reformulados():
    base = {"modo": "literal", "variante": "completa", "latencia_cliente_ms": 1000, "fuentes_sobrantes": 0,
            "correcto": True, "costo_usd": 0.01, "resultado": "respondio"}
    resultados = [
        {**base, "caso_id": "A", "pregunta_limpia": True, "pregunta_limpia_ayudo": True},
        {**base, "caso_id": "B", "pregunta_limpia": True, "pregunta_limpia_ayudo": False, "resultado": "sin_informacion"},
        {**base, "caso_id": "C", "pregunta_limpia": False, "pregunta_limpia_ayudo": False},
        {**base, "caso_id": "N1", "pregunta_limpia": True, "pregunta_limpia_ayudo": False, "negativo_de_pregunta_limpia": True},
        {**base, "caso_id": "N2", "pregunta_limpia": False, "pregunta_limpia_ayudo": False, "negativo_de_pregunta_limpia": True},
    ]
    r = lb.resumen_respuestas(resultados)["literal"]
    assert r["segundos_intentos"] == 3
    assert r["segundos_intentos_con_resultados"] == 1
    assert r["negativos_reformulados"] == ["N1"]


def test_resumen_respuestas_sin_dato_de_pregunta_limpia_no_falla():
    base = {"modo": "literal", "variante": "completa", "latencia_cliente_ms": 1000, "fuentes_sobrantes": 0,
            "correcto": True, "costo_usd": 0.01, "resultado": "respondio"}
    r = lb.resumen_respuestas([{**base, "caso_id": "A"}])["literal"]  # corridas anteriores a la 008
    assert r["segundos_intentos"] == 0 and r["negativos_reformulados"] == []


def test_comparar_ignora_la_pregunta_limpia_desconocida_en_una_corrida():
    a = {"puntajes": None, "respuestas": {"resultados": [_resp("A", "literal", 0.01, 1000)]}}
    b = {"puntajes": None, "respuestas": {"resultados": [{**_resp("A", "literal", 0.01, 1000), "pregunta_limpia": True,
                                                          "pregunta_limpia_ayudo": True}]}}
    assert lb.comparar(a, b)["cambios"] == []
    # Conocida en las dos corridas, un cambio sí se informa.
    c = {"puntajes": None, "respuestas": {"resultados": [{**_resp("A", "literal", 0.01, 1000), "pregunta_limpia": False,
                                                          "pregunta_limpia_ayudo": False}]}}
    assert any("pregunta_limpia" in x for x in lb.comparar(c, b)["cambios"])


def test_parejas_incluye_la_variante_limpia_si_existe():
    meds = [
        _med("S", "respuesta", [0.70]),
        _med("S", "respuesta", [0.85], variante="corta"),
        _med("S", "respuesta", [0.84], variante="limpia"),
    ]
    fila = lb.parejas(meds, 0.82)[0]
    assert fila["limpia"]["distancia_umbral"] == 0.02


def test_el_informe_cuenta_los_segundos_intentos_sin_guion_largo():
    mediciones = [_med("A", "respuesta", [0.9], 0.9)]
    for m in mediciones:
        m["por_modo"] = {k: lb.resultado_por_modo(m["candidatos"], 8, 0.82) for k in lb.MODOS}
    contexto = {
        "etiqueta": "t", "fecha": "2026-10-15T10:00:00", "commit": "abc1234567", "cambios_sin_confirmar": False,
        "destino": "produccion", "umbral": 0.82, "limite_literal": 8, "limite_razonamiento": 16,
        "candidatos_pedidos": 50, "proveedor_embeddings": "local", "dimension": 384,
        "fragmentos_por_dominio": {"P / D": 10}, "casos_omitidos": [],
    }
    base = {"variante": "completa", "modo": "literal", "resultado": "respondio", "correcto": True,
            "fuentes_mostradas": 1, "fuentes_sobrantes": 0, "latencia_cliente_ms": 1000, "costo_usd": 0.001}
    resultados = [
        {**base, "caso_id": "A", "pregunta_limpia": True, "pregunta_limpia_ayudo": True},
        {**base, "caso_id": "N1", "pregunta_limpia": True, "pregunta_limpia_ayudo": False,
         "negativo_de_pregunta_limpia": True},
    ]
    respuestas = {
        "contexto": {"fecha": "2026-10-15T10:05:00", "destino": "produccion", "artefacto": "Prueba",
                     "modos": ["literal"], "tope_usd": 0.2, "casos_omitidos": []},
        "resultados": resultados, "parcial": False, "motivo_parada": None, "gasto_total_usd": 0.002,
        "resumen": lb.resumen_respuestas(resultados),
    }
    corrida = {
        "puntajes": {"contexto": contexto, "mediciones": mediciones,
                     "resumen": lb.resumen_puntajes(mediciones, 0.82, {"literal": 8, "razonamiento": 16})},
        "respuestas": respuestas,
    }
    texto = lb.generar_informe(corrida)
    assert "Segundos intentos: 2; con resultados: 1; negativos reformulados: N1" in texto
    assert chr(0x2014) not in texto


def test_correr_respuestas_registra_el_texto_de_la_pregunta_limpia():
    notas = {
        "q-1": "Pregunta limpia: «Natalia Soto Solís» (con resultados)",
        "q-2": "Pregunta limpia: «a; b (c)» (sin resultados); Respuesta cortada: se reintentó",
        "q-3": None,
    }

    def consultar(caso, variante, modo):
        cuerpo = _body(docs=("acta.pdf",))
        cuerpo["id"] = {"A": "q-1", "B": "q-2"}.get(caso["id"], "q-3")
        return 200, cuerpo, 100

    corrida = lb.correr_respuestas(
        [_caso(id="A"), _caso(id="B"), _caso(id="C")], ["literal"], consultar,
        lambda consulta_id: {"cost_usd": 0.01, "reject_reason": notas[consulta_id]}, 1.0,
    )
    por_caso = {r["caso_id"]: r["pregunta_limpia_texto"] for r in corrida["resultados"]}
    assert por_caso == {"A": "Natalia Soto Solís", "B": "a; b (c)", "C": None}
    assert {r["caso_id"]: r["pregunta_limpia_ayudo"] for r in corrida["resultados"]} == {"A": True, "B": False, "C": False}


def test_el_texto_de_la_pregunta_limpia_es_nulo_sin_detalle_de_uso_y_comparar_lo_ignora_si_falta():
    corrida = lb.correr_respuestas(
        [_caso()], ["literal"], lambda c, v, m: (200, _body(docs=("acta.pdf",)), 1), lambda _id: None, 1.0
    )
    assert corrida["resultados"][0]["pregunta_limpia_texto"] is None
    a = {"puntajes": None, "respuestas": {"resultados": [_resp("A", "literal", 0.01, 1000)]}}
    b = {"puntajes": None, "respuestas": {"resultados": [{**_resp("A", "literal", 0.01, 1000),
                                                          "pregunta_limpia_texto": "Natalia"}]}}
    assert lb.comparar(a, b)["cambios"] == []
    c = {"puntajes": None, "respuestas": {"resultados": [{**_resp("A", "literal", 0.01, 1000),
                                                          "pregunta_limpia_texto": "Otro"}]}}
    assert any("pregunta_limpia_texto" in x for x in lb.comparar(c, b)["cambios"])


# --- Feature 009: reranker local ---------------------------------------------------------------


def _cr(*pares):
    """Candidatos puntuados por el reranker: (documento, logit) en el orden de coseno."""
    from mia.rag.rerank import sigmoid

    filas = [
        {"posicion": i, "documento": doc, "dominio": "P / D", "logit": logit, "puntaje": sigmoid(logit)}
        for i, (doc, logit) in enumerate(pares, start=1)
    ]
    ordenados = sorted(filas, key=lambda f: -f["logit"])
    for rango, fila in enumerate(ordenados, start=1):
        fila["posicion_rerank"] = rango
    return filas


def test_puesto_rerank_da_el_puesto_por_coseno_y_por_reranker_del_documento_esperado():
    candidatos = _cr(("otro-1.pdf", -5.0), ("otro-2.pdf", -6.0), ("acta-07.pdf", 8.0))
    [fila] = lb.puesto_rerank(candidatos, ["acta-07"])
    assert fila["fragmento"] == "acta-07"
    assert (fila["posicion"], fila["posicion_rerank"]) == (3, 1)
    assert fila["puntaje_rerank"] > 0.999 and fila["logit"] == 8.0


def test_puesto_rerank_elige_el_mejor_fragmento_del_documento_y_marca_ausentes():
    candidatos = _cr(("acta-07.pdf", -2.0), ("otro.pdf", -9.0), ("acta-07.pdf", 3.0))
    asi = lb.puesto_rerank(candidatos, ["acta-07", "inexistente"])
    assert asi[0]["posicion"] == 3 and asi[0]["posicion_rerank"] == 1
    assert asi[1] == {
        "fragmento": "inexistente", "posicion": None, "posicion_rerank": None, "puntaje_rerank": None, "logit": None,
        "entra": {},
    }


def test_puesto_rerank_dice_si_el_esperado_entra_en_cada_modo():
    candidatos = _cr(*[(f"o{i}.pdf", 5.0 - i * 0.1) for i in range(10)], ("acta.pdf", 4.0))  # puesto 11 de 11 por reranker
    [fila] = lb.puesto_rerank(candidatos, ["acta"], minimo=0.5, limites={"literal": 8, "razonamiento": 16})
    assert fila["posicion_rerank"] == 11
    assert fila["entra"] == {"literal": False, "razonamiento": True}
    [bajo] = lb.puesto_rerank(_cr(("acta.pdf", -3.0)), ["acta"], minimo=0.5, limites={"literal": 8})
    assert bajo["entra"] == {"literal": False}  # no llega al mínimo del reranker


def test_resultado_por_modo_rerank():
    candidatos = _cr(*[(f"o{i}.pdf", 2.0) for i in range(12)], ("x.pdf", -8.0))
    assert lb.resultado_por_modo_rerank(candidatos, 8, 0.5) == {
        "pasan": 8, "mejor_puntaje": pytest.approx(0.8808, abs=1e-3), "resultado": "responde",
    }
    assert lb.resultado_por_modo_rerank(candidatos, 16, 0.5)["pasan"] == 12
    sin = lb.resultado_por_modo_rerank(_cr(("a.pdf", -3.0), ("b.pdf", -6.0)), 8, 0.5)
    assert sin["resultado"] == "sin_informacion" and sin["pasan"] == 0
    assert lb.resultado_por_modo_rerank([], 8, 0.5) == {"pasan": 0, "mejor_puntaje": None, "resultado": "sin_informacion"}


def _med_r(caso_id, espera, candidatos, documentos=(), variante="completa", grupo=None):
    return {
        "caso_id": caso_id, "variante": variante, "espera": espera, "grupo": grupo,
        "rerank": {"candidatos": candidatos, "esperados": lb.puesto_rerank(candidatos, list(documentos))},
    }


def test_ventana_rerank_con_y_sin_ventana():
    separables = [
        _med_r("R1", "respuesta", _cr(("acta.pdf", 6.0), ("x.pdf", -7.0)), ["acta"]),
        _med_r("R2", "respuesta", _cr(("y.pdf", -8.0), ("acta2.pdf", 1.0)), ["acta2"]),
        _med_r("N1", "sin_informacion", _cr(("a.pdf", -5.0), ("b.pdf", -6.0))),
        _med_r("N2", "sin_informacion", _cr(("a.pdf", -6.5))),
    ]
    v = lb.ventana_rerank(separables)
    assert v["max_sin_info_caso"] == "N1" and v["min_respuesta_caso"] == "R2"
    assert v["max_sin_info_logit"] == -5.0 and v["min_respuesta_logit"] == 1.0
    assert v["separables"] is True and v["rango_logit"] == [-5.0, 1.0]
    mezclados = [*separables[:2], _med_r("N3", "sin_informacion", _cr(("a.pdf", 3.0)))]
    v2 = lb.ventana_rerank(mezclados)
    assert v2["separables"] is False and v2["rango_logit"] is None
    assert v2["max_sin_info_caso"] == "N3"


def test_ventana_rerank_lista_los_ausentes_y_no_cuenta_las_otras_variantes():
    mediciones = [
        _med_r("R1", "respuesta", _cr(("x.pdf", -7.0)), ["acta"]),  # el esperado no está entre los candidatos
        _med_r("R2", "respuesta", _cr(("acta.pdf", 5.0)), ["acta"]),
        _med_r("R2", "respuesta", _cr(("acta.pdf", -9.0)), ["acta"], variante="corta"),
    ]
    v = lb.ventana_rerank(mediciones)
    assert v["ausentes"] == ["R1"] and v["min_respuesta_logit"] == 5.0


def test_barrido_minimos_cuenta_respuestas_y_sin_informacion_por_minimo():
    mediciones = [
        _med_r("R1", "respuesta", _cr(("acta.pdf", 6.0)), ["acta"]),
        _med_r("R2", "respuesta", _cr(("acta.pdf", 0.0)), ["acta"]),
        _med_r("N1", "sin_informacion", _cr(("a.pdf", -5.0))),
        _med_r("N2", "sin_informacion", _cr(("a.pdf", 1.0))),
    ]
    filas = {round(f["logit"]): f for f in lb.barrido_minimos(mediciones)}
    assert filas[-6]["sin_info_que_pasan"] == ["N1", "N2"] and filas[-6]["responden"] == ["R1", "R2"]
    assert filas[0]["sin_info_que_pasan"] == ["N2"] and filas[0]["responden"] == ["R1", "R2"]
    assert filas[2]["sin_info_que_pasan"] == [] and filas[2]["responden"] == ["R1"]
    assert filas[2]["no_responden"] == ["R2"] and filas[2]["sin_info_bloqueados"] == 2
    assert 0 < filas[0]["minimo"] < 1 and filas[0]["minimo"] == pytest.approx(0.5)


def test_barrido_minimos_acepta_una_lista_de_minimos():
    mediciones = [_med_r("R1", "respuesta", _cr(("acta.pdf", 6.0)), ["acta"])]
    filas = lb.barrido_minimos(mediciones, minimos=[0.5, 0.99999])
    assert [f["minimo"] for f in filas] == [0.5, 0.99999]
    assert filas[0]["responden"] == ["R1"] and filas[1]["no_responden"] == ["R1"]


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("Reranker: mejor 0.987, 3 de 30 sobre el mínimo 0.50",
         {"mejor": 0.987, "candidatos": 30, "sobre_minimo": 3, "cayo": False, "ninguno": False}),
        ("Reranker: ninguno sobre el mínimo 0.50, mejor 0.003 de 30",
         {"mejor": 0.003, "candidatos": 30, "sobre_minimo": 0, "cayo": False, "ninguno": True}),
        ("Reranker no disponible: se usó la similitud",
         {"mejor": None, "candidatos": None, "sobre_minimo": None, "cayo": True, "ninguno": False}),
        ("Reranker: mejor 1.000, 1 de 2 sobre el mínimo 0.50; Pregunta limpia: «X» (con resultados)",
         {"mejor": 1.0, "candidatos": 2, "sobre_minimo": 1, "cayo": False, "ninguno": False}),
        ("Fuentes: sin citas utilizables", None),
        (None, None),
    ],
)
def test_leer_nota_rerank(texto, esperado):
    assert lb.leer_nota_rerank(texto) == esperado


def test_correr_respuestas_registra_las_notas_del_reranker():
    notas = {
        "q-pasa": "Reranker: mejor 0.987, 3 de 30 sobre el mínimo 0.50",
        "q-ninguno": "Reranker: ninguno sobre el mínimo 0.50, mejor 0.003 de 30",
        "q-cae": "Reranker no disponible: se usó la similitud",
        "q-sin": None,
    }

    def consultar(caso, variante, modo):
        cuerpo = _body(docs=("acta.pdf",))
        cuerpo["id"] = {"A": "q-pasa", "B": "q-ninguno", "C": "q-cae"}.get(caso["id"], "q-sin")
        return 200, cuerpo, 100

    corrida = lb.correr_respuestas(
        [_caso(id="A"), _caso(id="B"), _caso(id="C"), _caso(id="D")], ["literal"], consultar,
        lambda consulta_id: {"cost_usd": 0.01, "reject_reason": notas[consulta_id]}, 1.0,
    )
    por_caso = {
        r["caso_id"]: (r["rerank_mejor"], r["rerank_cayo"], r["rerank_ninguno_sobre_minimo"]) for r in corrida["resultados"]
    }
    assert por_caso == {"A": (0.987, False, False), "B": (0.003, False, True), "C": (None, True, False), "D": (None, False, False)}
    sin_detalle = lb.correr_respuestas(
        [_caso()], ["literal"], lambda c, v, m: (200, _body(docs=("acta.pdf",)), 1), lambda _id: None, 1.0
    )["resultados"][0]
    assert sin_detalle["rerank_cayo"] is None and sin_detalle["rerank_ninguno_sobre_minimo"] is None


def test_resumen_respuestas_cuenta_las_consultas_con_reranker_y_las_caidas():
    base = {"modo": "literal", "variante": "completa", "latencia_cliente_ms": 1000, "fuentes_sobrantes": 0,
            "correcto": True, "costo_usd": 0.01, "resultado": "respondio"}
    resultados = [
        {**base, "caso_id": "A", "rerank_mejor": 0.9, "rerank_cayo": False, "rerank_ninguno_sobre_minimo": False},
        {**base, "caso_id": "B", "rerank_mejor": 0.1, "rerank_cayo": False, "rerank_ninguno_sobre_minimo": True,
         "resultado": "sin_informacion"},
        {**base, "caso_id": "C", "rerank_mejor": None, "rerank_cayo": True, "rerank_ninguno_sobre_minimo": False},
        {**base, "caso_id": "D", "rerank_mejor": None, "rerank_cayo": False, "rerank_ninguno_sobre_minimo": False},
    ]
    r = lb.resumen_respuestas(resultados)["literal"]
    assert (r["consultas_con_reranker"], r["caidas_a_coseno"], r["ninguno_sobre_minimo"]) == (3, 1, 1)
    sin = lb.resumen_respuestas([{**base, "caso_id": "A"}])["literal"]  # corridas anteriores a la 009
    assert (sin["consultas_con_reranker"], sin["caidas_a_coseno"], sin["ninguno_sobre_minimo"]) == (0, 0, 0)


def test_comparar_ignora_las_notas_del_reranker_desconocidas_y_informa_las_conocidas():
    a = {"puntajes": None, "respuestas": {"resultados": [_resp("A", "literal", 0.01, 1000)]}}
    b = {"puntajes": None, "respuestas": {"resultados": [
        {**_resp("A", "literal", 0.01, 1000), "rerank_cayo": False, "rerank_ninguno_sobre_minimo": False}]}}
    assert lb.comparar(a, b)["cambios"] == []
    c = {"puntajes": None, "respuestas": {"resultados": [
        {**_resp("A", "literal", 0.01, 1000), "rerank_cayo": True, "rerank_ninguno_sobre_minimo": False}]}}
    assert any("rerank_cayo" in x for x in lb.comparar(b, c)["cambios"])


def test_el_informe_menciona_las_consultas_con_reranker():
    resultados = [{"modo": "literal", "variante": "completa", "latencia_cliente_ms": 1000, "fuentes_sobrantes": 0,
                   "correcto": True, "costo_usd": 0.01, "resultado": "respondio", "caso_id": "A",
                   "rerank_mejor": 0.9, "rerank_cayo": True, "rerank_ninguno_sobre_minimo": False}]
    resumen = lb.resumen_respuestas(resultados)
    corrida = {
        "puntajes": {
            "contexto": {
                "etiqueta": "e", "fecha": "f", "commit": "0123456789abc", "cambios_sin_confirmar": False, "destino": "d",
                "umbral": 0.82, "limite_literal": 8, "limite_razonamiento": 16, "candidatos_pedidos": 50,
                "proveedor_embeddings": "local", "dimension": 384, "fragmentos_por_dominio": {},
            },
            "mediciones": [],
            "resumen": {
                "ventana_separacion": {
                    "max_sin_info": None, "max_sin_info_caso": None, "max_sin_info_sin_aislamiento": None,
                    "max_sin_info_sin_aislamiento_caso": None, "min_respuesta": None, "min_respuesta_caso": None,
                    "separables": False, "rango": None, "ausentes": [],
                },
                "parejas": [], "barrido_umbrales": {"literal": [], "razonamiento": []},
            },
        },
        "respuestas": {
            "contexto": {"fecha": "f", "destino": "d", "modos": ["literal"], "tope_usd": 1, "artefacto": "a"},
            "resultados": resultados, "resumen": resumen, "gasto_total_usd": 0.01, "parcial": False,
        },
    }
    assert "Consultas con reranker: 1; caídas a coseno: 1; sin candidatos sobre el mínimo: 0" in lb.generar_informe(corrida)


def test_resumen_rendimiento_calcula_percentiles_y_si_cumple():
    medidas = [200.0, 250.0, 300.0, 350.0, 400.0, 450.0, 480.0, 490.0, 495.0, 1200.0]
    r = lb.resumen_rendimiento(medidas, p50_max_ms=500, p95_max_ms=1500)
    assert r["n"] == 10 and r["p50_ms"] == 400.0 and r["p95_ms"] == 1200.0 and r["cumple"] is True
    lento = lb.resumen_rendimiento([900.0, 1000.0, 1100.0, 1200.0], p50_max_ms=500, p95_max_ms=1500)
    assert lento["cumple"] is False
    assert lb.resumen_rendimiento([], 500, 1500) == {"n": 0, "p50_ms": None, "p95_ms": None, "cumple": False}


class _Resultado:
    def __init__(self, chunk_id, doc, score, texto):
        self.chunk_id, self.document_id, self.domain, self.score, self.text = chunk_id, doc, "dom", score, texto


class _AlmacenFalso:
    def __init__(self, resultados):
        self.resultados, self.llamadas = resultados, []

    def search(self, vector, domains, limit):
        self.llamadas.append(limit)
        return self.resultados[:limit]


class _EmbedderFalso:
    def embed(self, textos, is_query=False):
        return [[0.0, 1.0]]


class _RerankerFalso:
    def __init__(self):
        self.llamadas = []

    def score(self, query, passages, deadline=None):
        self.llamadas.append((query, list(passages)))
        return [float(len(p)) - 5 for p in passages]  # más largo, más puntaje


def test_medir_caso_rerank_puntua_contra_la_pregunta_pedida_y_numera_los_puestos():
    resultados = [
        _Resultado("c1", "d1", 0.90, "corto"), _Resultado("c2", "d2", 0.85, "un texto mucho más largo"),
        _Resultado("c3", "d3", 0.70, "mediano!!"),
    ]
    reranker = _RerankerFalso()
    tiempos = iter([10.0, 10.25])
    filas, ms = lb.medir_caso_rerank(
        "Natalia", "¿Quién es Natalia?", ["dom"], _EmbedderFalso(), _AlmacenFalso(resultados),
        {"d1": "a.pdf", "d2": "b.pdf", "d3": "c.pdf"}, {"dom": "P / D"}, reranker, 30, reloj=lambda: next(tiempos),
    )
    assert reranker.llamadas[0][0] == "¿Quién es Natalia?"  # la API puntúa con la pregunta completa
    assert ms == pytest.approx(250.0)
    assert [(f["documento"], f["posicion"], f["posicion_rerank"]) for f in filas] == [
        ("a.pdf", 1, 3), ("b.pdf", 2, 1), ("c.pdf", 3, 2),
    ]
    assert filas[1]["puntaje_coseno"] == 0.85 and filas[1]["dominio"] == "P / D" and 0 < filas[1]["puntaje"] <= 1


def test_medir_caso_rerank_sin_resultados_no_invoca_al_reranker():
    reranker = _RerankerFalso()
    vacio, ms = lb.medir_caso_rerank("x", "x", ["dom"], _EmbedderFalso(), _AlmacenFalso([]), {}, {}, reranker, 30)
    assert vacio == [] and ms == 0.0 and reranker.llamadas == []


def test_medir_combinacion_descarta_el_calentamiento_y_repite():
    reranker = _RerankerFalso()
    reloj = iter(x * 0.1 for x in range(100))
    medidas = lb.medir_combinacion(reranker, [("p1", ["a"]), ("p2", ["b"])], 3, reloj=lambda: next(reloj))
    assert len(reranker.llamadas) == 2 + 3 * 2  # una pasada de calentamiento y tres repeticiones
    assert len(medidas) == 6 and all(m == pytest.approx(100.0) for m in medidas)


def test_el_informe_incluye_la_seccion_del_reranker_si_se_midio():
    candidatos = _cr(("x.pdf", -6.0), ("acta.pdf", 7.0))
    medicion = {
        "caso_id": "R1", "variante": "completa", "categoria": "mvp", "espera": "respuesta", "grupo": None,
        "candidatos": [{"posicion": 1, "puntaje": 0.8, "documento": "x.pdf", "dominio": "P / D"}],
        "por_modo": {m: {"pasan": 0, "mejor_puntaje": 0.8, "resultado": "sin_informacion"} for m in lb.MODOS},
        "esperados": [{"fragmento": "acta", "posicion": None, "puntaje": None}],
        "rerank": {
            "candidatos": candidatos, "ms": 812.0,
            "por_modo": {m: lb.resultado_por_modo_rerank(candidatos, 8, 0.5) for m in lb.MODOS},
            "esperados": lb.puesto_rerank(candidatos, ["acta"], 0.5, {"literal": 8, "razonamiento": 16}),
        },
    }
    resumen_p = {
        "ventana_separacion": {
            "max_sin_info": None, "max_sin_info_caso": None, "max_sin_info_sin_aislamiento": None,
            "max_sin_info_sin_aislamiento_caso": None, "min_respuesta": None, "min_respuesta_caso": None,
            "separables": False, "rango": None, "ausentes": [],
        },
        "parejas": [], "barrido_umbrales": {"literal": [], "razonamiento": []},
        "barrido_minimos": lb.barrido_minimos([medicion]), "ventana_rerank": lb.ventana_rerank([medicion]),
    }
    corrida = {
        "puntajes": {
            "contexto": {
                "etiqueta": "e", "fecha": "f", "commit": "0123456789abc", "cambios_sin_confirmar": False, "destino": "d",
                "umbral": 0.82, "limite_literal": 8, "limite_razonamiento": 16, "candidatos_pedidos": 50,
                "proveedor_embeddings": "local", "dimension": 384, "fragmentos_por_dominio": {},
                "reranker": {"modelo": "m", "candidatos": 30, "minimo": 0.5,
                             "tokens_por_pasaje": 192, "hilos": 2},
            },
            "mediciones": [medicion], "resumen": resumen_p,
        },
        "respuestas": None,
    }
    informe = lb.generar_informe(corrida)
    assert "## Reranker local (feature 009)" in informe
    assert "#2 -> #1" in informe and "Barrido del mínimo" in informe
    assert "¿Algún mínimo separa ambos grupos?: sí" in informe or "¿Algún mínimo separa ambos grupos?: no" in informe


def test_puntajes_sin_rerank_no_agrega_la_seccion():
    from_vacio = {"mediciones": [], "contexto": {}, "resumen": {}}
    assert lb._seccion_rerank(from_vacio) == []


# --- Feature 009: convergencia (comparar con reranker, regresiones por mínimo, registro del servidor) ----------


def _med_comp(caso_id, candidatos, documentos=("acta",), variante="completa", espera="respuesta", coseno=(0.80,)):
    """Medición con coseno y reranker, para comparar corridas."""
    return {
        "caso_id": caso_id, "variante": variante, "categoria": "mvp", "espera": espera, "grupo": None,
        "candidatos": [
            {"posicion": i, "puntaje": p, "documento": "acta-01.pdf" if i == 1 else f"o{i}.pdf", "dominio": "P / D"}
            for i, p in enumerate(coseno, start=1)
        ],
        "por_modo": {m: {"pasan": 0, "mejor_puntaje": coseno[0], "resultado": "sin_informacion"} for m in lb.MODOS},
        "esperados": lb.posicion_esperados(
            [{"posicion": i, "puntaje": p, "documento": "acta-01.pdf" if i == 1 else f"o{i}.pdf"}
             for i, p in enumerate(coseno, start=1)], list(documentos)),
        "rerank": {
            "candidatos": candidatos, "ms": 100.0,
            "por_modo": {m: lb.resultado_por_modo_rerank(candidatos, 8, 0.06) for m in lb.MODOS},
            "esperados": lb.puesto_rerank(candidatos, list(documentos), 0.06, {"literal": 8, "razonamiento": 16}),
        },
    }


def _corrida_p(*mediciones, fragmentos=None):
    return {"puntajes": {"contexto": {"fragmentos_por_dominio": fragmentos or {}}, "mediciones": list(mediciones)},
            "respuestas": None}


def test_comparar_informa_los_cambios_del_reranker_entre_dos_corridas():
    a = _corrida_p(_med_comp("EN2", _cr(("x.pdf", -7.0), ("acta-01.pdf", -9.0))))
    b = _corrida_p(_med_comp("EN2", _cr(("x.pdf", -7.0), ("acta-01.pdf", 3.0))))
    cambios = lb.comparar(a, b)["cambios"]
    assert any("EN2" in c and "reranker" in c and "literal" in c and "sin_informacion -> responde" in c for c in cambios)
    assert any("EN2" in c and "puesto" in c and "#2 -> #1" in c for c in cambios)
    assert any("EN2" in c and "mejor puntaje" in c and "reranker" in c for c in cambios)


def test_comparar_no_informa_cambios_del_reranker_si_son_iguales_ni_si_falta_en_una_corrida():
    candidatos = _cr(("x.pdf", -7.0), ("acta-01.pdf", 3.0))
    a = _corrida_p(_med_comp("EN2", candidatos))
    b = _corrida_p(_med_comp("EN2", candidatos))
    assert lb.comparar(a, b)["cambios"] == []
    sin_rerank = _med_comp("EN2", candidatos)
    del sin_rerank["rerank"]
    assert lb.comparar(_corrida_p(sin_rerank), b)["cambios"] == []  # corridas anteriores a la 009
    assert lb.comparar(b, _corrida_p(sin_rerank))["cambios"] == []


def test_barrido_minimos_informa_regresiones_y_mejoras_frente_al_coseno():
    # R1: hoy encuentra su documento (coseno 0,90, puesto 1) y el reranker lo puntúa muy bajo: regresión con mínimo alto.
    # R2: hoy no lo encuentra (coseno 0,80) y el reranker lo puntúa alto: mejora.
    r1 = _med_comp("R1", _cr(("acta-01.pdf", -5.0)), coseno=(0.90,))
    r2 = _med_comp("R2", _cr(("acta-01.pdf", 4.0)), coseno=(0.80,))
    filas = {round(f["logit"]): f for f in lb.barrido_minimos(
        [r1, r2], umbral=0.82, limites={"literal": 8, "razonamiento": 16})}
    assert filas[-6]["regresiones"] == [] and filas[-6]["mejoras"] == ["R2"]
    assert filas[0]["regresiones"] == ["R1"] and filas[0]["mejoras"] == ["R2"]


def test_barrido_minimos_sin_umbral_no_calcula_regresiones_y_exige_el_limite_del_modo():
    filas = lb.barrido_minimos([_med_comp("R1", _cr(("acta-01.pdf", 4.0)), coseno=(0.90,))])
    assert all(f["regresiones"] == [] and f["mejoras"] == [] for f in filas)
    # Con límites, un documento fuera de los primeros `limite` por reranker no cuenta como que responde.
    candidatos = _cr(*[(f"o{i}.pdf", 5.0) for i in range(8)], ("acta-01.pdf", 4.0))
    medicion = _med_comp("R3", candidatos, coseno=(0.80,))
    fila = {round(f["logit"]): f for f in lb.barrido_minimos(
        [medicion], umbral=0.82, limites={"literal": 8, "razonamiento": 16})}[0]
    assert fila["responden"] == [] and fila["no_responden"] == ["R3"]


_REGISTRO = """\
INFO:     mia.rag.rerank: Reranker cargado: RSS 366 -> 524 MB, pico 593 MB
INFO:     mia.api.routes.query: Reranker: 20 candidatos en 300 ms, pico de memoria 600 MB (modo literal)
INFO:     mia.api.routes.query: Fin de la generación: stop (modo literal)
INFO:     mia.api.routes.query: Reranker: 20 candidatos en 320 ms, pico de memoria 610 MB (modo razonamiento)
INFO:     mia.api.routes.query: Reranker: 30 candidatos en 2000 ms, pico de memoria ? MB (modo literal)
WARNING:  mia.rag.rerank: El reranker falló (RerankTimeout: tarde): la consulta usa la similitud de vectores
"""


def test_resumir_registro_cuenta_puntuaciones_latencia_memoria_y_avisos():
    r = lb.resumir_registro(_REGISTRO, p50_max_ms=500, p95_max_ms=1500)
    assert r["puntuaciones"] == 3 and r["candidatos"] == [20, 30]
    assert r["latencia"]["p50_ms"] == 320 and r["latencia"]["p95_ms"] == 2000 and r["latencia"]["cumple"] is False
    assert r["pico_mb_maximo"] == 610
    assert r["cargas"] == [{"rss_antes_mb": 366, "rss_despues_mb": 524, "pico_mb": 593}]
    assert r["avisos_de_fallo"] == 1


def test_resumir_registro_sin_lineas_del_reranker():
    r = lb.resumir_registro("INFO: otra cosa\n", 500, 1500)
    assert r["puntuaciones"] == 0 and r["latencia"]["p50_ms"] is None and r["pico_mb_maximo"] is None
    assert r["cargas"] == [] and r["avisos_de_fallo"] == 0


def test_comando_registro_lee_un_archivo_e_imprime_el_resumen(tmp_path, capsys):
    archivo = tmp_path / "logs.txt"
    archivo.write_text(_REGISTRO, encoding="utf-8")
    assert lb.main(["registro", "--archivo", str(archivo)]) == 0
    salida = capsys.readouterr().out
    assert "3 puntuaciones" in salida and "p50 320 ms" in salida and "consultas: 610 MB" in salida
    assert lb.main(["registro", "--archivo", str(tmp_path / "no-existe.txt")]) == 2


# --- Búsqueda por palabras (feature 010) ---------------------------------------------------------------------------


def test_los_casos_versionados_incluyen_al_menos_12_nuevos_la_mitad_sin_respuesta():
    casos = lb.cargar_casos()
    nuevos = [c for c in casos if c["id"].startswith(("HB", "HS"))]
    assert len(nuevos) >= 12
    assert sum(1 for c in nuevos if c["espera"] == "sin_informacion") >= len(nuevos) // 2 - 1
    assert sum(1 for c in nuevos if c["espera"] == "sin_informacion") >= 6
    assert all(c.get("nota") for c in nuevos)


def _FragmentoP(chunk_id, doc, score):
    from mia.storage.vector_store import SearchResult

    return SearchResult(chunk_id=chunk_id, document_id=doc, domain="d1", text="", score=score, chunk_index=0)


class _AlmacenPalabras:
    """Índice de palabras (palabra a ids), fragmentos con su coseno y una búsqueda por significado fija."""

    def __init__(self, indice, fragmentos, vectores):
        self.indice, self.fragmentos, self.vectores = indice, fragmentos, vectores
        self.llamadas = []

    def match_chunks(self, domains, text, limit):
        self.llamadas.append(text)
        return list(self.indice.get(text, []))[:limit]

    def score_chunks(self, embedding, domains, chunk_ids):
        return [self.fragmentos[i] for i in chunk_ids if i in self.fragmentos]

    def search(self, vector, domains, limit):
        return self.vectores[:limit]


AJUSTES = {"frecuencia": 60, "limite": 20, "ranuras": 3, "grupos_max": 8, "largo_min": 3, "rrf_k": 60}
LIMITES = {"literal": 8, "razonamiento": 16}
ARCHIVOS_P = {"doc-j": "IPA Joseph Obando Sandi.pdf", "doc-k": "Acta 04.pdf", "doc-v": "Otro.pdf"}


def _medir_joseph(indice=None, vectores=None):
    fragmentos = {"j1": _FragmentoP("j1", "doc-j", 0.78), "k1": _FragmentoP("k1", "doc-k", 0.7)}
    almacen = _AlmacenPalabras(
        indice or {"joseph": ["j1", "k1"], "obando": ["j1"], "sandi": []}, fragmentos,
        vectores if vectores is not None else [_FragmentoP("v1", "doc-v", 0.9)],
    )
    medicion = lb.medir_palabras(
        "¿Quién es Joseph Obando Sandí?", ["d1"], [0.1], almacen, ARCHIVOS_P, [], AJUSTES, LIMITES, 0.82,
        ["Joseph Obando"], reloj=iter([0.0, 0.5]).__next__,
    )
    return medicion, almacen


def test_medir_palabras_trae_el_documento_que_el_significado_no_traia():
    medicion, _ = _medir_joseph()
    assert [g["terminos"] for g in medicion["grupos"]] == [["joseph"], ["obando"], ["sandi"]]
    assert [g["fragmentos"] for g in medicion["grupos"]] == [2, 1, 0]
    assert medicion["especificos"] == 3 and len(medicion["candidatos"]) == 1
    assert medicion["candidatos"][0]["documento"] == "IPA Joseph Obando Sandi.pdf"
    assert medicion["candidatos"][0]["coincidentes"] == 2 and medicion["ms"] == 500.0
    for modo in lb.MODOS:
        d = medicion["por_modo"][modo]
        assert d["antes"]["pasan"] == 1  # el fragmento de coseno 0,90 pasa el umbral
        assert d["despues"]["pasan"] == 2
        esperado = d["esperados"][0]
        assert esperado["puesto_antes"] is None and esperado["puesto_despues"] == 2
        assert esperado["traido_por"] == "palabras"
    # Con ranuras en 0 el documento no entra: lo dice el barrido.
    assert medicion["barrido_ranuras"]["0"]["literal"]["esperado"] is False
    assert medicion["barrido_ranuras"]["3"]["literal"]["esperado"] is True
    assert medicion["barrido_frecuencia"]["60"] == {"especificos": 3, "candidatos": 1, "esperado": True}
    assert set(medicion["barrido_frecuencia"]) == {"20", "40", "60", "100", "200"}
    # No se guarda texto de fragmentos.
    assert "texto" not in json.dumps(medicion)


def test_medir_palabras_de_una_persona_inventada_no_deja_candidatos():
    medicion, _ = _medir_joseph({"zacarias": [], "fernandez": ["k1"], "pizarro": []})
    assert medicion["candidatos"] == [] and medicion["especificos"] == 3
    assert medicion["por_modo"]["literal"]["despues"] == medicion["por_modo"]["literal"]["antes"]
    assert medicion["barrido_frecuencia"]["20"]["candidatos"] == 0


def test_resumen_palabras_cuenta_objetivos_sin_informacion_y_barridos():
    mejora, _ = _medir_joseph()
    sin_candidatos, _ = _medir_joseph({"joseph": [], "obando": [], "sandi": []}, vectores=[])
    medicion_a = {"caso_id": "S22-3", "variante": "completa", "categoria": "seccion_2_2", "espera": "respuesta",
                  "palabras": mejora}
    medicion_b = {"caso_id": "EN7", "variante": "completa", "categoria": "envoltura", "espera": "sin_informacion",
                  "palabras": sin_candidatos}
    # Un caso sin respuesta que sí recibe candidatos léxicos y pasa de "sin información" a responder.
    peligro, _ = _medir_joseph(vectores=[])
    medicion_c = {"caso_id": "HS3", "variante": "completa", "categoria": "sin_respuesta", "espera": "sin_informacion",
                  "palabras": peligro}
    resumen = lb.resumen_palabras([medicion_a, medicion_b, medicion_c])
    literal = resumen["por_modo"]["literal"]
    assert literal["objetivos"] == 1 and literal["con_esperado_antes"] == 0 and literal["con_esperado_despues"] == 1
    assert literal["mejoran"] == ["S22-3"] and literal["empeoran"] == []
    assert literal["bus1_bus2"] == {"preguntas": 1, "pasan_antes": 0, "pasan_despues": 1}
    assert literal["sin_info_que_llegan_al_modelo"] == ["HS3"]
    assert resumen["barrido_frecuencia"]["60"] == {"objetivos_acertados": 1, "sin_info_con_candidatos": ["HS3"]}
    assert resumen["barrido_ranuras"]["0"]["literal"]["objetivos_con_esperado"] == 0
    assert resumen["barrido_ranuras"]["3"]["literal"]["objetivos_con_esperado"] == 1
    assert resumen["latencia_ms"]["n"] == 3


def test_comparar_detecta_los_cambios_por_la_busqueda_por_palabras():
    mejora, _ = _medir_joseph()
    base = {
        "caso_id": "S22-3", "variante": "completa", "candidatos": _cand(0.78),
        "por_modo": {m: {"pasan": 0, "mejor_puntaje": 0.78, "resultado": "sin_informacion"} for m in lb.MODOS},
        "esperados": [{"fragmento": "Joseph Obando", "posicion": 5, "puntaje": 0.78}],
    }
    hibrida = {**base, "palabras": mejora}
    contexto = {"fragmentos_por_dominio": {}}
    a = {"puntajes": {"contexto": contexto, "mediciones": [base]}}
    b = {"puntajes": {"contexto": contexto, "mediciones": [hibrida]}}
    cambios = lb.comparar(a, b)["cambios"]
    assert any("modo literal: resultado con búsqueda por palabras sin_informacion -> responde" in c for c in cambios)
    # Dos corridas iguales no cambian nada.
    assert lb.comparar(b, b)["cambios"] == []


def test_leer_la_nota_de_la_busqueda_hibrida_y_resumir_las_respuestas():
    assert lb.leer_nota_hibrida("Búsqueda híbrida: 3 por palabras, 1 nuevos") == {"candidatos": 3, "nuevos": 1, "cayo": False}
    assert lb.leer_nota_hibrida("Búsqueda por palabras no disponible: se usó el significado")["cayo"] is True
    assert lb.leer_nota_hibrida("Reranker: mejor 0.5") is None and lb.leer_nota_hibrida(None) is None
    filas = [
        {"hibrida_candidatos": 2, "hibrida_nuevos": 1, "hibrida_cayo": False},
        {"hibrida_candidatos": None, "hibrida_nuevos": None, "hibrida_cayo": True},
        {"hibrida_candidatos": None, "hibrida_nuevos": None, "hibrida_cayo": False},
    ]
    assert lb._resumen_hibrida(filas) == {"consultas_con_hibrida": 1, "hibrida_nuevos_total": 1, "caidas_a_significado": 1}


def test_registro_resume_la_latencia_de_espera_y_fusion_frente_a_sus_limites():
    registro = (
        "INFO: mia.api.routes.query: Búsqueda híbrida: 4 grupos (3 específicos), 2 candidatos, 1 nuevos; hilo 30 ms, "
        "espera y fusión 12 ms (modo literal)\n"
        "INFO: mia.api.routes.query: Búsqueda híbrida: 2 grupos (1 específicos), 0 candidatos, 0 nuevos; hilo 80 ms, "
        "espera y fusión 150 ms (modo razonamiento)\n"
        "WARNING: mia.rag.lexical: La búsqueda por palabras falló (RuntimeError: x): la consulta usa el significado\n"
    )
    r = lb.resumir_registro(registro, 500, 1500)["hibrida"]
    assert r["consultas"] == 2 and r["con_candidatos"] == 1 and r["avisos_de_fallo"] == 1
    assert r["espera_y_fusion"]["p50_ms"] == 12 and r["espera_y_fusion"]["cumple"] is True
    assert r["hilo"]["p95_ms"] is not None
    lento = lb.resumir_registro_hibrida(
        "Búsqueda híbrida: 1 grupos (1 específicos), 1 candidatos, 1 nuevos; hilo 900 ms, espera y fusión 700 ms (modo literal)"
    )
    assert lento["espera_y_fusion"]["cumple"] is False


def test_cargar_equivalencias_de_un_archivo_o_las_semillas(tmp_path):
    ruta = tmp_path / "eq.json"
    ruta.write_text(json.dumps([["TFG", "Trabajo Final de Graduación"]]), encoding="utf-8")
    [equivalencia] = lb.cargar_equivalencias(None, str(ruta))
    assert (equivalencia.sigla, equivalencia.form) == ("tfg", "trabajo final de graduacion")
    assert {e.sigla for e in lb.cargar_equivalencias(None, None)} == {"tfg", "mgti"}


def test_el_cliente_de_solo_lectura_deja_pasar_scroll_y_rechaza_escrituras():
    from unittest.mock import MagicMock

    cliente = lb.ClienteSoloLectura(MagicMock())
    cliente.scroll(collection_name="c")
    with pytest.raises(PermissionError):
        cliente.upsert(collection_name="c", points=[])
    with pytest.raises(PermissionError):
        cliente.create_payload_index(collection_name="c")
