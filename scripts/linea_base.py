"""Línea base de la búsqueda de MIA: mide cómo se comporta hoy la recuperación y la respuesta.

No forma parte del producto y no lo modifica. Ver specs/005-linea-base-busqueda/.

Subcomandos:
    inventario  Lista dominios, documentos y fragmentos (solo lectura).
    puntajes    Puntajes de similitud por caso, barrido de umbrales y ventana de separación
                (solo lectura, sin tokens de modelos).
                Con --rerank agrega el puntaje del reranker local (feature 009): puesto del documento esperado,
                barrido del mínimo y ventana de separación (sin tokens de modelos de lenguaje).
    rendimiento Memoria y latencia del reranker local por candidatos, tokens por pasaje e hilos (feature 009).
    respuestas  Corre los casos contra POST /query: fuentes, tiempo y costo (gasta; exige --tope-usd).
    informe     Genera el informe en Markdown de una corrida.
    comparar    Compara dos corridas caso por caso.

Uso:
    python scripts/linea_base.py inventario --env-file .env.produccion
    python scripts/linea_base.py puntajes --etiqueta base --env-file .env.produccion
    python scripts/linea_base.py respuestas --etiqueta base --url https://mia-main.up.railway.app --tope-usd 0.50
    python scripts/linea_base.py informe base --salida docs/LINEA_BASE_BUSQUEDA.md
    python scripts/linea_base.py comparar base base-2

Nunca guarda ni imprime el texto de los fragmentos ni el de las respuestas. La salida cruda queda en
tmp/linea_base/ (ignorado por git). Las claves se leen de .env (MIA_ARTIFACT_KEY y MIA_ADMIN_KEY).
"""

import argparse
import json
import math
import os
import re
import statistics
import subprocess
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
RUTA_CASOS = RAIZ / "scripts" / "datos" / "casos_busqueda.json"
SALIDA = RAIZ / "tmp" / "linea_base"

CATEGORIAS = {"mvp", "seccion_2_2", "indirecta", "sigla", "sin_respuesta", "lista_larga", "envoltura"}
ESPERAS = {"respuesta", "sin_informacion"}
MODOS = ("literal", "razonamiento")
SEPARADOR = " / "
NO_INFO_PREFIX = "No encontré información suficiente"
# Nota que la API deja en `reject_reason` cuando rigió la regla de seguridad de las citas (feature 006).
NOTA_REGLA_DE_SEGURIDAD = "Fuentes: sin citas utilizables"
# Notas de la feature 007 en `reject_reason` y aviso al final de una respuesta con posible corte.
NOTA_REINTENTO = "Respuesta cortada: se reintentó"
NOTA_AVISO_DE_CORTE = "Respuesta cortada: se entregó con aviso"
AVISO_DE_CORTE = "Aviso: la respuesta pudo quedar incompleta."
# Nota de la feature 008 en `reject_reason`: «Pregunta limpia: «texto» (con resultados)» o «(sin resultados)».
PATRON_PREGUNTA_LIMPIA = re.compile(r"Pregunta limpia: «(.*?)» \((con|sin) resultados\)", re.DOTALL)
# Notas de la feature 009 en `reject_reason`: el puntaje del reranker o la caída a la similitud.
PATRON_RERANK_CON = re.compile(r"Reranker: mejor (\d\.\d{3}), (\d+) de (\d+) sobre el mínimo \d\.\d{2}")
PATRON_RERANK_NINGUNO = re.compile(r"Reranker: ninguno sobre el mínimo \d\.\d{2}, mejor (\d\.\d{3}) de (\d+)")
NOTA_RERANK_CAIDA = "Reranker no disponible: se usó la similitud"
# Una respuesta que no termina con uno de estos caracteres es una candidata a corte que el modelo no declaró.
CIERRES_DE_FRASE = ".!?):;\"'”»*"

# Candidatos que se piden a la base vectorial por pregunta (máximo que acepta QUERY_SEARCH_LIMIT).
CANDIDATOS = 50
# Barrido de umbrales, en centésimas para no acumular errores de coma flotante.
BARRIDO_DESDE, BARRIDO_HASTA, BARRIDO_PASO = 60, 90, 1
# Diferencia de puntaje que se considera un cambio entre corridas (SC-007).
TOLERANCIA = 0.001

# Reintentos ante 502: el proveedor de modelos se satura a veces.
REINTENTOS = 3
ESPERA_REINTENTO = 20


class ErrorMedicion(Exception):
    """Una medición que no se puede hacer (configuración, conexión, sin casos). `main` la convierte en código 2."""


def _nfc(texto: str) -> str:
    # Los nombres de archivo con tildes pueden venir en NFD según el sistema que los subió.
    return unicodedata.normalize("NFC", texto)


def _contiene(nombre: str, fragmento: str) -> bool:
    return _nfc(fragmento).casefold() in _nfc(nombre).casefold()


# ---------------------------------------------------------------------------
# Casos, entorno y salida
# ---------------------------------------------------------------------------


def cargar_casos(ruta: Path = RUTA_CASOS) -> list[dict]:
    """Lee y valida el conjunto de casos (campos en specs/005-linea-base-busqueda/data-model.md)."""
    casos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    if not isinstance(casos, list) or not casos:
        raise ValueError("El archivo de casos debe ser una lista con al menos un caso.")
    vistos: set[str] = set()
    for caso in casos:
        id_ = caso.get("id")
        if not id_:
            raise ValueError(f"Hay un caso sin id: {caso}")
        if id_ in vistos:
            raise ValueError(f"Caso {id_}: id repetido.")
        vistos.add(id_)
        if caso.get("categoria") not in CATEGORIAS:
            raise ValueError(f"Caso {id_}: categoría inválida {caso.get('categoria')!r}.")
        if not caso.get("dominios") or not isinstance(caso["dominios"], list):
            raise ValueError(f"Caso {id_}: faltan los dominios.")
        if not caso.get("pregunta"):
            raise ValueError(f"Caso {id_}: falta la pregunta.")
        if caso.get("espera") not in ESPERAS:
            raise ValueError(f"Caso {id_}: espera inválida {caso.get('espera')!r}.")
        if caso["espera"] == "respuesta" and not caso.get("documentos"):
            raise ValueError(f"Caso {id_}: espera respuesta pero no declara los documentos que aportan.")
        if "sin_pregunta_limpia" in caso and not isinstance(caso["sin_pregunta_limpia"], bool):
            raise ValueError(f"Caso {id_}: sin_pregunta_limpia debe ser verdadero o falso.")
        if caso["categoria"] == "lista_larga" and not caso.get("contiene"):
            raise ValueError(f"Caso {id_}: una lista larga debe declarar en `contiene` el último ítem esperado.")
    return casos


def cargar_env(ruta: str | Path, sobrescribir: bool = True) -> int:
    """Exporta en os.environ las variables de un archivo tipo .env. Devuelve cuántas cargó.

    Con `sobrescribir` el archivo gana sobre lo que ya hubiera exportado (así se usa --env-file); si no,
    solo completa lo que falta (así se leen las claves de .env). Debe llamarse antes de importar `mia`.
    """
    ruta = Path(ruta)
    if not ruta.is_file():
        return 0
    cargadas = 0
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        if linea.startswith("export "):
            linea = linea.removeprefix("export ").strip()
        nombre, _, valor = linea.partition("=")
        nombre, valor = nombre.strip(), valor.strip()
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
            valor = valor[1:-1]
        if sobrescribir or nombre not in os.environ:
            os.environ[nombre] = valor
            cargadas += 1
    return cargadas


def _git(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], cwd=RAIZ, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def destino_de(url: str) -> str:
    """`local` o `produccion` según el host; nunca se guarda la URL completa ni claves."""
    host = re.sub(r"^\w+://", "", url).split("/")[0].split(":")[0].split("@")[-1]
    return "local" if host in {"localhost", "127.0.0.1", "::1", ""} else "produccion"


def contexto_corrida(etiqueta: str, destino: str, **extra) -> dict:
    """Contexto de una corrida (FR-014): fecha, código, destino y los parámetros que se le pasen."""
    return {
        "etiqueta": etiqueta,
        "fecha": datetime.now().astimezone().isoformat(timespec="seconds"),
        "commit": _git("rev-parse", "HEAD"),
        "cambios_sin_confirmar": bool(_git("status", "--porcelain")),
        "destino": destino,
        **extra,
    }


def carpeta_de(contexto: dict) -> Path:
    marca = datetime.fromisoformat(contexto["fecha"]).strftime("%Y%m%d-%H%M%S")
    return SALIDA / f"{marca}-{contexto['etiqueta']}"


def guardar_json(carpeta: Path, nombre: str, datos: dict) -> Path:
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / nombre
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return ruta


def leer_corrida(etiqueta: str, base: Path = SALIDA) -> dict:
    """Carga la corrida más reciente con esa etiqueta: {carpeta, puntajes, respuestas}."""
    patron = re.compile(r"^\d{8}-\d{6}-(.+)$")
    candidatas = sorted(
        p for p in base.glob("*") if p.is_dir() and (m := patron.match(p.name)) and m.group(1) == etiqueta
    )
    if not candidatas:
        raise FileNotFoundError(f"No hay ninguna corrida con la etiqueta '{etiqueta}' en {base}.")
    corrida: dict = {"carpeta": candidatas[-1], "puntajes": None, "respuestas": None}
    # `puntajes` y `respuestas` se corren por separado y quedan en carpetas distintas: de cada una se
    # toma la más reciente que tenga ese archivo.
    for nombre in ("puntajes", "respuestas"):
        for carpeta in reversed(candidatas):
            ruta = carpeta / f"{nombre}.json"
            if ruta.is_file():
                corrida[nombre] = json.loads(ruta.read_text(encoding="utf-8"))
                break
    return corrida


# ---------------------------------------------------------------------------
# Lógica pura de puntajes
# ---------------------------------------------------------------------------


def resultado_por_modo(candidatos: list[dict], limite: int, umbral: float) -> dict:
    """Lo que decidiría la API: responde si algún candidato de los primeros `limite` alcanza el umbral
    (`relevant = [r for r in results if r.score >= threshold]`), si no, "sin información" sin llamar al modelo."""
    visibles = [c for c in candidatos if c["posicion"] <= limite]
    pasan = sum(1 for c in visibles if c["puntaje"] >= umbral)
    return {
        "pasan": pasan,
        "mejor_puntaje": max((c["puntaje"] for c in visibles), default=None),
        "resultado": "responde" if pasan else "sin_informacion",
    }


def posicion_esperados(candidatos: list[dict], documentos: list[str]) -> list[dict]:
    """Por cada fragmento de nombre de `documentos`: posición y puntaje del mejor candidato de ese
    documento, o None si no aparece entre los candidatos."""
    salida = []
    for fragmento in documentos:
        coinciden = [c for c in candidatos if _contiene(c["documento"], fragmento)]
        if coinciden:
            mejor = max(coinciden, key=lambda c: c["puntaje"])
            salida.append(
                {"fragmento": fragmento, "posicion": mejor["posicion"], "puntaje": mejor["puntaje"]}
            )
        else:
            salida.append({"fragmento": fragmento, "posicion": None, "puntaje": None})
    return salida


def _completas(mediciones: list[dict]) -> list[dict]:
    return [m for m in mediciones if m["variante"] == "completa"]


def barrido_umbrales(mediciones: list[dict], umbral_actual: float, limites: dict[str, int]) -> dict:
    """Por modo y por umbral candidato, qué casos cambian de resultado frente al umbral actual."""
    barrido: dict[str, list[dict]] = {}
    for modo, limite in limites.items():
        base = {
            m["caso_id"]: resultado_por_modo(m["candidatos"], limite, umbral_actual)["resultado"]
            for m in _completas(mediciones)
        }
        filas = []
        for centesimas in range(BARRIDO_DESDE, BARRIDO_HASTA + 1, BARRIDO_PASO):
            umbral = centesimas / 100
            a_responder, a_sin_info = [], []
            for m in _completas(mediciones):
                nuevo = resultado_por_modo(m["candidatos"], limite, umbral)["resultado"]
                if nuevo != base[m["caso_id"]]:
                    (a_responder if nuevo == "responde" else a_sin_info).append(m["caso_id"])
            filas.append(
                {"umbral": umbral, "pasan_a_responder": a_responder, "pasan_a_sin_info": a_sin_info}
            )
        barrido[modo] = filas
    return barrido


def ventana_separacion(mediciones: list[dict]) -> dict:
    """Si algún umbral separa los casos que esperan respuesta de los que esperan "sin información" (BUS-3).

    `max_sin_info`: mayor mejor puntaje entre los casos "sin información" (incluidos los de aislamiento
    de dominio, grupo I). `min_respuesta`: menor puntaje del mejor documento esperado entre los casos que
    esperan respuesta. Los casos con el documento esperado ausente entre los candidatos se listan aparte.
    """
    sin_info, sin_info_aislamiento, respuesta, ausentes = [], [], [], []
    for m in _completas(mediciones):
        if not m["candidatos"]:
            mejor = 0.0
        else:
            mejor = max(c["puntaje"] for c in m["candidatos"])
        if m["espera"] == "sin_informacion":
            sin_info.append((mejor, m["caso_id"]))
            if m.get("grupo") != "I":
                sin_info_aislamiento.append((mejor, m["caso_id"]))
        else:
            puntajes = [e["puntaje"] for e in m["esperados"] if e["puntaje"] is not None]
            if puntajes:
                respuesta.append((max(puntajes), m["caso_id"]))
            else:
                ausentes.append(m["caso_id"])
    max_sin = max(sin_info, default=(None, None))
    max_sin_estricto = max(sin_info_aislamiento, default=(None, None))
    min_resp = min(respuesta, default=(None, None))
    separables = (
        max_sin[0] is not None and min_resp[0] is not None and min_resp[0] > max_sin[0]
    )
    return {
        "max_sin_info": max_sin[0],
        "max_sin_info_caso": max_sin[1],
        "max_sin_info_sin_aislamiento": max_sin_estricto[0],
        "max_sin_info_sin_aislamiento_caso": max_sin_estricto[1],
        "min_respuesta": min_resp[0],
        "min_respuesta_caso": min_resp[1],
        "separables": separables,
        "rango": [max_sin[0], min_resp[0]] if separables else None,
        "ausentes": ausentes,
    }


# Mínimos del reranker que recorre el barrido, en la escala del logit (el puntaje es su sigmoide y se satura).
BARRIDO_RERANK_LOGITS = tuple(range(-8, 9))


def puesto_rerank(candidatos: list[dict], documentos: list[str], minimo: float | None = None,
                  limites: dict[str, int] | None = None) -> list[dict]:
    """Por cada fragmento de nombre de `documentos`: puesto por coseno y por reranker, y puntaje del mejor candidato de
    ese documento (el de mayor puntaje del reranker), o todo None si no aparece entre los candidatos.

    Con `minimo` y `limites` agrega `entra`: por modo, si ese candidato llegaría al modelo (está entre los primeros
    `limite` por reranker y supera el mínimo)."""
    salida = []
    for fragmento in documentos:
        coinciden = [c for c in candidatos if _contiene(c["documento"], fragmento)]
        if not coinciden:
            salida.append({"fragmento": fragmento, "posicion": None, "posicion_rerank": None, "puntaje_rerank": None,
                           "logit": None, "entra": {}})
            continue
        mejor = max(coinciden, key=lambda c: c["logit"])
        entra = {}
        if minimo is not None and limites:
            entra = {m: mejor["posicion_rerank"] <= limite and mejor["puntaje"] >= minimo for m, limite in limites.items()}
        salida.append({"fragmento": fragmento, "posicion": mejor["posicion"], "posicion_rerank": mejor["posicion_rerank"],
                       "puntaje_rerank": mejor["puntaje"], "logit": mejor["logit"], "entra": entra})
    return salida


def resultado_por_modo_rerank(candidatos: list[dict], limite: int, minimo: float) -> dict:
    """Lo que decidiría la API con el reranker: responde si algún candidato supera el mínimo; al modelo llegan como
    mucho `limite` fragmentos."""
    sobre = [c for c in candidatos if c["puntaje"] >= minimo]
    return {
        "pasan": min(len(sobre), limite),
        "mejor_puntaje": max((c["puntaje"] for c in candidatos), default=None),
        "resultado": "responde" if sobre else "sin_informacion",
    }


def _sigmoide(x: float) -> float:
    from mia.rag.rerank import sigmoid

    return sigmoid(x)


def _con_rerank(mediciones: list[dict]) -> list[dict]:
    return [m for m in _completas(mediciones) if m.get("rerank") is not None]


def barrido_minimos(mediciones: list[dict], minimos: list[float] | None = None) -> list[dict]:
    """Por mínimo del reranker, qué casos con respuesta responderían y qué casos de "sin información" pasarían.

    Sin `minimos` recorre el logit de -8 a 8 (el puntaje se satura y una malla uniforme en 0 a 1 no separa nada).
    Un caso responde si su mejor candidato supera el mínimo; para los casos con respuesta además se pide que el
    documento esperado esté entre los candidatos y lo supere."""
    if minimos is None:
        mallas = [(x, _sigmoide(x)) for x in BARRIDO_RERANK_LOGITS]
    else:
        mallas = [(None, m) for m in minimos]
    filas = []
    for logit, minimo in mallas:
        responden, no_responden, sin_info_que_pasan, bloqueados = [], [], [], 0
        for m in _con_rerank(mediciones):
            candidatos = m["rerank"]["candidatos"]
            if m["espera"] == "sin_informacion":
                if any(c["puntaje"] >= minimo for c in candidatos):
                    sin_info_que_pasan.append(m["caso_id"])
                else:
                    bloqueados += 1
            else:
                esperados = m["rerank"].get("esperados") or []
                pasa = any(e["puntaje_rerank"] is not None and e["puntaje_rerank"] >= minimo for e in esperados)
                (responden if pasa else no_responden).append(m["caso_id"])
        filas.append({"minimo": minimo, "logit": logit, "responden": responden, "no_responden": no_responden,
                      "sin_info_que_pasan": sin_info_que_pasan, "sin_info_bloqueados": bloqueados})
    return filas


def ventana_rerank(mediciones: list[dict]) -> dict:
    """Si algún mínimo del reranker separa los casos con respuesta de los de "sin información" (BUS-3), como
    `ventana_separacion` pero con el puntaje del reranker (comparado en logit para que la saturación no empate)."""
    sin_info, respuesta, ausentes = [], [], []
    for m in _con_rerank(mediciones):
        candidatos = m["rerank"]["candidatos"]
        if m["espera"] == "sin_informacion":
            sin_info.append((max((c["logit"] for c in candidatos), default=float("-inf")), m["caso_id"]))
        else:
            logits = [e["logit"] for e in (m["rerank"].get("esperados") or []) if e["logit"] is not None]
            if logits:
                respuesta.append((max(logits), m["caso_id"]))
            else:
                ausentes.append(m["caso_id"])
    max_sin = max(sin_info, default=(None, None))
    min_resp = min(respuesta, default=(None, None))
    separables = max_sin[0] is not None and min_resp[0] is not None and min_resp[0] > max_sin[0]
    return {
        "max_sin_info_logit": max_sin[0], "max_sin_info": None if max_sin[0] is None else _sigmoide(max_sin[0]),
        "max_sin_info_caso": max_sin[1],
        "min_respuesta_logit": min_resp[0], "min_respuesta": None if min_resp[0] is None else _sigmoide(min_resp[0]),
        "min_respuesta_caso": min_resp[1],
        "separables": separables,
        "rango_logit": [max_sin[0], min_resp[0]] if separables else None,
        "ausentes": ausentes,
    }


def leer_nota_rerank(texto: str | None) -> dict | None:
    """Datos de la nota del reranker en `reject_reason`, o None si no hay nota."""
    if not texto:
        return None
    if NOTA_RERANK_CAIDA in texto:
        return {"mejor": None, "candidatos": None, "sobre_minimo": None, "cayo": True, "ninguno": False}
    con = PATRON_RERANK_CON.search(texto)
    if con:
        return {"mejor": float(con.group(1)), "candidatos": int(con.group(3)), "sobre_minimo": int(con.group(2)),
                "cayo": False, "ninguno": False}
    ninguno = PATRON_RERANK_NINGUNO.search(texto)
    if ninguno:
        return {"mejor": float(ninguno.group(1)), "candidatos": int(ninguno.group(2)), "sobre_minimo": 0,
                "cayo": False, "ninguno": True}
    return None


def resumen_rendimiento(medidas_ms: list[float], p50_max_ms: float, p95_max_ms: float) -> dict:
    """p50 y p95 de una lista de latencias y si cumplen los límites de la feature 009 (SC-006)."""
    p50, p95 = percentil(medidas_ms, 50), percentil(medidas_ms, 95)
    cumple = p50 is not None and p95 is not None and p50 <= p50_max_ms and p95 <= p95_max_ms
    return {"n": len(medidas_ms), "p50_ms": p50, "p95_ms": p95, "cumple": cumple}


def variante_limpia(caso: dict) -> str | None:
    """La pregunta limpia del caso (feature 008), o None si no aplica o ya es la variante corta del caso.

    Se calcula con el mismo código que usa la API, así que `puntajes` anticipa sin costo qué buscaría el
    segundo intento.
    """
    from mia.rag.query_rewrite import clean_question

    limpia = clean_question(caso["pregunta"])
    if limpia is None or limpia == caso.get("variante_corta"):
        return None
    return limpia


def parejas(mediciones: list[dict], umbral: float) -> list[dict]:
    """Pregunta completa y variante corta lado a lado (y la limpia, si se midió), con su distancia al umbral."""
    por_caso: dict[str, dict[str, dict]] = {}
    for m in mediciones:
        por_caso.setdefault(m["caso_id"], {})[m["variante"]] = m
    filas = []
    for caso_id, variantes in por_caso.items():
        if "completa" not in variantes or "corta" not in variantes:
            continue
        fila = {"caso_id": caso_id}
        for nombre in ("completa", "corta", "limpia"):
            if nombre not in variantes:
                continue
            candidatos = variantes[nombre]["candidatos"]
            mejor = max((c["puntaje"] for c in candidatos), default=None)
            fila[nombre] = {
                "mejor_puntaje": mejor,
                "distancia_umbral": None if mejor is None else round(mejor - umbral, 4),
            }
        filas.append(fila)
    return filas


def resumen_puntajes(mediciones: list[dict], umbral: float, limites: dict[str, int]) -> dict:
    return {
        "barrido_umbrales": barrido_umbrales(mediciones, umbral, limites),
        "ventana_separacion": ventana_separacion(mediciones),
        "parejas": parejas(mediciones, umbral),
    }


# ---------------------------------------------------------------------------
# Lógica pura de respuestas
# ---------------------------------------------------------------------------


def evaluar_respuesta(caso: dict, status: int, body: dict) -> dict:
    """Resultado de una consulta contra el caso. No conserva la respuesta ni los extractos de las fuentes.

    `correcto` exige, si el caso espera respuesta, que no sea "sin información", que al menos uno de los
    documentos esperados esté entre las fuentes y que contenga el texto esperado; si espera "sin
    información", que lo sea y sin fuentes.
    """
    vacio = {
        "resultado": "no_concluyente",
        "correcto": False,
        "fuentes_mostradas": 0,
        "fuentes_esperadas_halladas": 0,
        "fuentes_sobrantes": 0,
        "documentos_mostrados": [],
        "contiene_ok": None,
        "termina_sin_puntuacion": None,
        "aviso_de_corte": None,
    }
    if status != 200:
        return vacio
    documentos = sorted({_nfc(s["document"]) for s in body.get("sources", [])})
    texto = body.get("answer", "")
    sin_info = bool(body.get("no_info")) or texto.startswith(NO_INFO_PREFIX)
    esperados = caso.get("documentos", []) if caso["espera"] == "respuesta" else []
    halladas = [f for f in esperados if any(_contiene(d, f) for d in documentos)]
    sobrantes = [d for d in documentos if not any(_contiene(d, f) for f in esperados)]
    contiene = caso.get("contiene")
    contiene_ok = None if not contiene else contiene.casefold() in texto.casefold()
    if caso["espera"] == "sin_informacion":
        correcto = sin_info and not documentos
    else:
        correcto = (not sin_info) and (not esperados or bool(halladas)) and contiene_ok is not False
    return {
        "resultado": "sin_informacion" if sin_info else "respondio",
        "correcto": correcto,
        "fuentes_mostradas": len(documentos),
        "fuentes_esperadas_halladas": len(halladas),
        "fuentes_sobrantes": len(sobrantes),
        "documentos_mostrados": documentos,
        "contiene_ok": contiene_ok,
        # Solo se conserva si la respuesta parece cortada, nunca su texto.
        "termina_sin_puntuacion": (not sin_info) and bool(texto.strip()) and texto.rstrip()[-1] not in CIERRES_DE_FRASE,
        "aviso_de_corte": AVISO_DE_CORTE in texto,
    }


def percentil(valores: list[float], p: float) -> float | None:
    """Percentil por rango más cercano, sin dependencias."""
    if not valores:
        return None
    ordenados = sorted(valores)
    rango = max(1, math.ceil(p / 100 * len(ordenados)))
    return ordenados[min(rango, len(ordenados)) - 1]


def _media(valores: list[float]) -> float | None:
    return sum(valores) / len(valores) if valores else None


def _resumen_cortes(filas: list[dict]) -> dict:
    """Reintentos, avisos de posible corte y respuestas que terminan sin puntuación (feature 007)."""
    con_contenido = [r for r in filas if r["resultado"] == "respondio"]

    def contar(campo):
        conocidas = [r for r in con_contenido if r.get(campo) is not None]
        n = sum(1 for r in conocidas if r[campo])
        return n, (n / len(conocidas) if conocidas else None)

    reintentos, p_reintentos = contar("reintento")
    avisos, p_avisos = contar("aviso_de_corte")
    sin_punto, p_sin_punto = contar("termina_sin_puntuacion")
    return {
        "reintentos": reintentos,
        "proporcion_reintentos": p_reintentos,
        "avisos_de_corte": avisos,
        "proporcion_avisos_de_corte": p_avisos,
        "terminan_sin_puntuacion": sin_punto,
        "proporcion_terminan_sin_puntuacion": p_sin_punto,
    }


def _resumen_pregunta_limpia(filas: list[dict]) -> dict:
    """Segundos intentos con la pregunta limpia, cuántos encontraron fragmentos y negativos reformulados (008)."""
    intentos = [r for r in filas if r.get("pregunta_limpia")]
    return {
        "segundos_intentos": len(intentos),
        "segundos_intentos_con_resultados": sum(1 for r in intentos if r.get("pregunta_limpia_ayudo")),
        "negativos_reformulados": [r["caso_id"] for r in intentos if r.get("negativo_de_pregunta_limpia")],
    }


def _resumen_rerank(filas: list[dict]) -> dict:
    """Consultas en las que intervino el reranker, cuántas cayeron a la similitud y cuántas no dejaron candidatos
    sobre el mínimo (feature 009)."""
    con_reranker = [r for r in filas if r.get("rerank_mejor") is not None or r.get("rerank_cayo")]
    return {
        "consultas_con_reranker": len(con_reranker),
        "caidas_a_coseno": sum(1 for r in filas if r.get("rerank_cayo")),
        "ninguno_sobre_minimo": sum(1 for r in filas if r.get("rerank_ninguno_sobre_minimo")),
    }


def _resumen_regla_de_seguridad(filas: list[dict]) -> dict:
    """Cuántas respuestas con contenido cayeron en la regla de seguridad de las citas (feature 006)."""
    con_contenido = [r for r in filas if r["resultado"] == "respondio" and r.get("regla_de_seguridad") is not None]
    aplicada = sum(1 for r in con_contenido if r["regla_de_seguridad"])
    return {
        "regla_de_seguridad_aplicada": aplicada,
        "proporcion_regla_de_seguridad": aplicada / len(con_contenido) if con_contenido else None,
    }


def resumen_respuestas(resultados: list[dict]) -> dict:
    """Resumen por modo de una corrida de `respuestas`."""
    resumen = {}
    for modo in MODOS:
        filas = [r for r in resultados if r["modo"] == modo]
        if not filas:
            continue
        concluyentes = [r for r in filas if r["resultado"] != "no_concluyente"]
        costos = [r["costo_usd"] for r in filas if r.get("costo_usd") is not None]
        costos_sin_info = [
            r["costo_usd"] for r in filas if r["resultado"] == "sin_informacion" and r.get("costo_usd") is not None
        ]
        cliente = [r["latencia_cliente_ms"] for r in concluyentes if r.get("latencia_cliente_ms") is not None]
        resumen[modo] = {
            "consultas": len(filas),
            "correctos": [r["caso_id"] for r in filas if r["correcto"]],
            "fallidos": [r["caso_id"] for r in concluyentes if not r["correcto"]],
            "no_concluyentes": [r["caso_id"] for r in filas if r["resultado"] == "no_concluyente"],
            "fuentes_sobrantes_promedio": _media([r["fuentes_sobrantes"] for r in concluyentes]),
            "latencia_p50_ms": percentil(cliente, 50),
            "latencia_p95_ms": percentil(cliente, 95),
            "costo_medio_usd": _media(costos),
            "costo_medio_sin_info_usd": _media(costos_sin_info),
            "gasto_total_usd": sum(costos),
            **_resumen_regla_de_seguridad(filas),
            **_resumen_cortes(filas),
            **_resumen_pregunta_limpia(filas),
            **_resumen_rerank(filas),
        }
    return resumen


def correr_respuestas(casos, modos, consultar, leer_costo, tope_usd: float) -> dict:
    """Recorre casos y modos acumulando el costo y deteniéndose al alcanzar el tope o ante un 429.

    `consultar(caso, variante, modo)` devuelve (status, body, latencia_cliente_ms) y `leer_costo(id)` el
    costo de esa consulta (dict o None). El sobregiro máximo es el de una consulta.
    """
    resultados: list[dict] = []
    gasto = 0.0
    parada = None
    for caso in casos:
        variantes = [("completa", caso["pregunta"])]
        if caso.get("variante_corta"):
            variantes.append(("corta", caso["variante_corta"]))
        for modo in modos:
            for variante, _ in variantes:
                if gasto >= tope_usd:
                    parada = "tope_usd"
                    break
                status, body, latencia = consultar(caso, variante, modo)
                if status == 429:
                    parada = "tope_diario_del_artefacto"
                    break
                if status in (401, 403):
                    parada = "clave_invalida_o_artefacto_desactivado"
                    break
                evaluacion = evaluar_respuesta(caso, status, body)
                consulta_id = body.get("id") if status == 200 else None
                costo = leer_costo(consulta_id) if consulta_id else None
                nota_limpia = PATRON_PREGUNTA_LIMPIA.search((costo or {}).get("reject_reason") or "")
                nota_rerank = leer_nota_rerank((costo or {}).get("reject_reason"))
                if costo and costo.get("cost_usd") is not None:
                    gasto += costo["cost_usd"]
                resultados.append(
                    {
                        "caso_id": caso["id"],
                        "variante": variante,
                        "modo": modo,
                        **evaluacion,
                        "latencia_cliente_ms": latencia,
                        "latencia_api_ms": body.get("latency_ms") if status == 200 else None,
                        "costo_usd": costo.get("cost_usd") if costo else None,
                        "costo_estimado": costo.get("cost_estimated") if costo else None,
                        "tokens": costo.get("tokens") if costo else None,
                        "regla_de_seguridad": (
                            None if not costo else NOTA_REGLA_DE_SEGURIDAD in (costo.get("reject_reason") or "")
                        ),
                        "reintento": None if not costo else NOTA_REINTENTO in (costo.get("reject_reason") or ""),
                        "aviso_de_corte": bool(evaluacion["aviso_de_corte"])
                        or NOTA_AVISO_DE_CORTE in ((costo or {}).get("reject_reason") or ""),
                        "pregunta_limpia": None if not costo else nota_limpia is not None,
                        "pregunta_limpia_ayudo": None if not costo else bool(nota_limpia and nota_limpia.group(2) == "con"),
                        "pregunta_limpia_texto": nota_limpia.group(1) if nota_limpia else None,
                        "negativo_de_pregunta_limpia": bool(caso.get("sin_pregunta_limpia")),
                        "rerank_mejor": nota_rerank["mejor"] if nota_rerank else None,
                        "rerank_cayo": None if not costo else bool(nota_rerank and nota_rerank["cayo"]),
                        "rerank_ninguno_sobre_minimo": None if not costo else bool(nota_rerank and nota_rerank["ninguno"]),
                        "consulta_id": consulta_id,
                    }
                )
            if parada:
                break
        if parada:
            break
    return {"resultados": resultados, "parcial": parada is not None, "motivo_parada": parada, "gasto_total_usd": gasto}


# ---------------------------------------------------------------------------
# Comparación e informe
# ---------------------------------------------------------------------------


# Datos que las corridas anteriores no registran: si falta en una de las dos, no cuenta como un cambio.
CAMPOS_OPCIONALES = {
    "regla_de_seguridad", "reintento", "aviso_de_corte", "termina_sin_puntuacion", "pregunta_limpia",
    "pregunta_limpia_ayudo", "pregunta_limpia_texto", "rerank_cayo", "rerank_ninguno_sobre_minimo",
}


def comparar(a: dict, b: dict) -> dict:
    """Diferencias entre dos corridas (cada una con "puntajes" y "respuestas", que pueden ser None)."""
    cambios: list[str] = []
    datos_distintos = False
    pa, pb = a.get("puntajes"), b.get("puntajes")
    if pa and pb:
        if pa["contexto"].get("fragmentos_por_dominio") != pb["contexto"].get("fragmentos_por_dominio"):
            datos_distintos = True
        ma = {(m["caso_id"], m["variante"]): m for m in pa["mediciones"]}
        mb = {(m["caso_id"], m["variante"]): m for m in pb["mediciones"]}
        for clave in sorted(ma.keys() | mb.keys()):
            x, y = ma.get(clave), mb.get(clave)
            nombre = f"{clave[0]} ({clave[1]})"
            if x is None or y is None:
                cambios.append(f"{nombre}: solo está en una de las corridas.")
                continue
            mejor_x = max((c["puntaje"] for c in x["candidatos"]), default=0.0)
            mejor_y = max((c["puntaje"] for c in y["candidatos"]), default=0.0)
            if abs(mejor_x - mejor_y) > TOLERANCIA:
                cambios.append(f"{nombre}: mejor puntaje {mejor_x:.4f} -> {mejor_y:.4f}.")
            for modo in MODOS:
                rx, ry = x["por_modo"][modo]["resultado"], y["por_modo"][modo]["resultado"]
                if rx != ry:
                    cambios.append(f"{nombre}, modo {modo}: resultado {rx} -> {ry}.")
    ra, rb = a.get("respuestas"), b.get("respuestas")
    medianas: dict = {}
    if ra and rb:
        xa = {(r["caso_id"], r["variante"], r["modo"]): r for r in ra["resultados"]}
        xb = {(r["caso_id"], r["variante"], r["modo"]): r for r in rb["resultados"]}
        for clave in sorted(xa.keys() & xb.keys()):
            x, y = xa[clave], xb[clave]
            nombre = f"{clave[0]} ({clave[1]}), modo {clave[2]}"
            campos = (
                "resultado", "correcto", "fuentes_mostradas", "fuentes_sobrantes", "regla_de_seguridad",
                "reintento", "aviso_de_corte", "termina_sin_puntuacion", "pregunta_limpia", "pregunta_limpia_ayudo",
                "pregunta_limpia_texto", "rerank_cayo", "rerank_ninguno_sobre_minimo",
            )
            for campo in campos:
                if campo in CAMPOS_OPCIONALES and (x.get(campo) is None or y.get(campo) is None):
                    continue  # dato desconocido en una de las corridas (p. ej. anteriores a la 006): no es un cambio
                if x.get(campo) != y.get(campo):
                    cambios.append(f"{nombre}: {campo} {x.get(campo)} -> {y.get(campo)}.")
        medianas = _medianas_de_razon(xa, xb)
    return {"cambios": cambios, "datos_distintos": datos_distintos, "medianas": medianas}


def _medianas_de_razon(xa: dict, xb: dict) -> dict:
    """Por modo, la mediana de la razón (B sobre A) de costo y de latencia caso por caso.

    El costo de una consulta con razonamiento varía mucho de una corrida a otra; la mediana de las
    razones por caso es más estable que el cociente de los promedios. Solo cuentan los casos con dato
    positivo en las dos corridas.
    """
    salida: dict = {}
    for modo in MODOS:
        claves = [k for k in xa.keys() & xb.keys() if k[2] == modo]
        razones_costo, razones_latencia = [], []
        for clave in claves:
            x, y = xa[clave], xb[clave]
            if (x.get("costo_usd") or 0) > 0 and (y.get("costo_usd") or 0) > 0:
                razones_costo.append(y["costo_usd"] / x["costo_usd"])
            if (x.get("latencia_cliente_ms") or 0) > 0 and (y.get("latencia_cliente_ms") or 0) > 0:
                razones_latencia.append(y["latencia_cliente_ms"] / x["latencia_cliente_ms"])
        if razones_costo or razones_latencia:
            salida[modo] = {
                "casos": len(razones_costo),
                "razon_costo": statistics.median(razones_costo) if razones_costo else None,
                "razon_latencia": statistics.median(razones_latencia) if razones_latencia else None,
            }
    return salida


def _fmt(valor, decimales: int = 3) -> str:
    if valor is None:
        return "-"
    if isinstance(valor, float):
        return f"{valor:.{decimales}f}"
    return str(valor)


def _seccion_rerank(puntajes: dict) -> list[str]:
    """Sección del informe con el reranker (feature 009); vacía si la corrida no lo midió."""
    mediciones = [m for m in puntajes["mediciones"] if m.get("rerank") is not None]
    if not mediciones:
        return []
    ctx = puntajes["contexto"].get("reranker") or {}
    resumen = puntajes["resumen"]
    lineas = [
        "## Reranker local (feature 009)",
        "",
        (
            f"Modelo {ctx.get('modelo', '?')}, {ctx.get('candidatos', '?')} candidatos, mínimo {ctx.get('minimo', '?')}, "
            f"piso de similitud {ctx.get('piso_de_similitud', '?')}, {ctx.get('tokens_por_pasaje', '?')} tokens por pasaje, "
            f"{ctx.get('hilos', '?')} hilos."
        ),
        "",
        "| Caso | Espera | Esperado: puesto coseno -> reranker | Puntaje del esperado | Mejor puntaje | Literal | Razonamiento | ms |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for m in mediciones:
        rr = m["rerank"]
        mejor = max((c["puntaje"] for c in rr["candidatos"]), default=None)
        if rr["esperados"]:
            puestos = ", ".join(
                "ausente" if e["posicion_rerank"] is None else f"#{e['posicion']} -> #{e['posicion_rerank']}"
                for e in rr["esperados"]
            )
            puntajes_esperado = ", ".join(_fmt(e["puntaje_rerank"]) for e in rr["esperados"])
        else:
            puestos, puntajes_esperado = "-", "-"
        lineas.append(
            f"| {m['caso_id']}" + ("" if m["variante"] == "completa" else f" ({m['variante']})")
            + f" | {m['espera']} | {puestos} | {puntajes_esperado} | {_fmt(mejor)} "
            f"| {rr['por_modo']['literal']['resultado']} | {rr['por_modo']['razonamiento']['resultado']} | {_fmt(rr['ms'], 0)} |"
        )
    w = resumen.get("ventana_rerank")
    if w:
        lineas += [
            "",
            (
                f"- Mayor puntaje entre los casos que esperan \"sin información\": logit {_fmt(w['max_sin_info_logit'], 2)} "
                f"(caso {w['max_sin_info_caso']})."
            ),
            (
                f"- Menor puntaje del documento esperado entre los casos que esperan respuesta: logit "
                f"{_fmt(w['min_respuesta_logit'], 2)} (caso {w['min_respuesta_caso']})."
            ),
            f"- ¿Algún mínimo separa ambos grupos?: {'sí, entre logit ' + _fmt(w['rango_logit'][0], 2) + ' y ' + _fmt(w['rango_logit'][1], 2) if w['separables'] else 'no'}.",
            "- Casos cuyo documento esperado no aparece entre los candidatos: " + (", ".join(w["ausentes"]) or "ninguno") + ".",
        ]
    barrido = resumen.get("barrido_minimos")
    if barrido:
        lineas += ["", "Barrido del mínimo (casos de la variante completa):", "",
                   "| Logit | Mínimo | Casos con respuesta que responden | Casos de \"sin información\" que pasarían |", "|---|---|---|---|"]
        for f in barrido:
            lineas.append(
                f"| {_fmt(f['logit'], 0)} | {_fmt(f['minimo'], 4)} | {len(f['responden'])} de {len(f['responden']) + len(f['no_responden'])} "
                f"| {', '.join(f['sin_info_que_pasan']) or 'ninguno'} |"
            )
    return [*lineas, ""]


def generar_informe(corrida: dict) -> str:
    """Markdown del informe de una corrida (puntajes y, si existe, respuestas)."""
    puntajes, respuestas = corrida.get("puntajes"), corrida.get("respuestas")
    if not puntajes:
        raise ValueError("La corrida no tiene puntajes.json: correr primero `puntajes`.")
    ctx = puntajes["contexto"]
    umbral = ctx["umbral"]
    limites = {"literal": ctx["limite_literal"], "razonamiento": ctx["limite_razonamiento"]}
    resumen = puntajes["resumen"]
    lineas = [
        "# Línea base de la búsqueda de MIA",
        "",
        (
            f"Generado de la corrida `{ctx['etiqueta']}` por `scripts/linea_base.py` (feature "
            "[005](../specs/005-linea-base-busqueda/spec.md)). No contiene texto de fragmentos ni de respuestas."
        ),
        "",
        "## Contexto de la corrida",
        "",
        f"- Fecha: {ctx['fecha']}",
        f"- Commit: `{ctx['commit'][:10]}`" + (" (con cambios sin confirmar)" if ctx["cambios_sin_confirmar"] else ""),
        f"- Destino: {ctx['destino']}",
        f"- Umbral de similitud declarado: {umbral}",
        f"- Resultados de búsqueda por modo: literal {limites['literal']}, razonamiento {limites['razonamiento']}",
        f"- Candidatos pedidos por pregunta: {ctx['candidatos_pedidos']}",
        f"- Embeddings: {ctx['proveedor_embeddings']} (dimensión {ctx['dimension']})",
        "- Fragmentos por dominio: "
        + "; ".join(f"{k}: {v}" for k, v in sorted(ctx["fragmentos_por_dominio"].items())),
    ]
    if ctx.get("casos_omitidos"):
        lineas.append("- Casos omitidos: " + ", ".join(f"{o['id']} ({o['motivo']})" for o in ctx["casos_omitidos"]))
    lineas += ["", "## Resultados por caso", ""]
    por_respuesta: dict[tuple, dict] = {}
    if respuestas:
        por_respuesta = {(r["caso_id"], r["variante"], r["modo"]): r for r in respuestas["resultados"]}
    cabecera = [
        "Caso", "Categoría", "Espera", "Mejor puntaje", "Posición esperado",
        "Literal (retrieval)", "Razonamiento (retrieval)",
    ]
    if respuestas:
        cabecera += ["Literal: correcto / sobrantes / s / USD", "Razonamiento: correcto / sobrantes / s / USD"]
    lineas.append("| " + " | ".join(cabecera) + " |")
    lineas.append("|" + "---|" * len(cabecera))
    for m in puntajes["mediciones"]:
        mejor = max((c["puntaje"] for c in m["candidatos"]), default=None)
        posiciones = [e["posicion"] for e in m["esperados"]]
        posicion = ", ".join(_fmt(p) if p is not None else "ausente" for p in posiciones) if posiciones else "-"
        fila = [
            m["caso_id"] + ("" if m["variante"] == "completa" else f" ({m['variante']})"),
            m["categoria"], m["espera"], _fmt(mejor), posicion,
            m["por_modo"]["literal"]["resultado"], m["por_modo"]["razonamiento"]["resultado"],
        ]
        if respuestas:
            for modo in MODOS:
                r = por_respuesta.get((m["caso_id"], m["variante"], modo))
                if r is None:
                    fila.append("-")
                else:
                    seg = None if r["latencia_cliente_ms"] is None else r["latencia_cliente_ms"] / 1000
                    fila.append(
                        f"{'sí' if r['correcto'] else 'NO'} / {r['fuentes_sobrantes']} / {_fmt(seg, 1)} / {_fmt(r['costo_usd'], 4)}"
                    )
        lineas.append("| " + " | ".join(fila) + " |")
    v = resumen["ventana_separacion"]
    lineas += [
        "",
        "## Ventana de separación (BUS-3)",
        "",
        f"- Mayor mejor puntaje entre los casos que esperan \"sin información\": {_fmt(v['max_sin_info'])} (caso {v['max_sin_info_caso']}).",
        f"- Sin contar los casos de aislamiento de dominio: {_fmt(v['max_sin_info_sin_aislamiento'])} (caso {v['max_sin_info_sin_aislamiento_caso']}).",
        f"- Menor puntaje del documento esperado entre los casos que esperan respuesta: {_fmt(v['min_respuesta'])} (caso {v['min_respuesta_caso']}).",
        f"- ¿Algún umbral separa ambos grupos?: {'sí, entre ' + _fmt(v['rango'][0]) + ' y ' + _fmt(v['rango'][1]) if v['separables'] else 'no'}.",
        "- Casos cuyo documento esperado no aparece entre los candidatos: " + (", ".join(v["ausentes"]) or "ninguno") + ".",
        "",
        *_seccion_rerank(puntajes),
        "## Pregunta completa frente a variante corta y pregunta limpia",
        "",
        "| Caso | Completa | Distancia al umbral | Corta | Distancia al umbral | Limpia | Distancia al umbral |",
        "|---|---|---|---|---|---|---|",
    ]
    for p in resumen["parejas"]:
        limpia = p.get("limpia") or {}
        lineas.append(
            f"| {p['caso_id']} | {_fmt(p['completa']['mejor_puntaje'])} | {_fmt(p['completa']['distancia_umbral'])} "
            f"| {_fmt(p['corta']['mejor_puntaje'])} | {_fmt(p['corta']['distancia_umbral'])} "
            f"| {_fmt(limpia.get('mejor_puntaje'))} | {_fmt(limpia.get('distancia_umbral'))} |"
        )
    lineas += ["", "## Barrido de umbrales", ""]
    for modo in MODOS:
        lineas += [f"Modo {modo} (casos cuyo resultado cambia frente a {umbral}):", ""]
        lineas += ["| Umbral | Pasan a responder | Pasan a \"sin información\" |", "|---|---|---|"]
        # Los umbrales consecutivos con el mismo resultado se agrupan en un rango.
        grupos: list[list] = []
        for fila in resumen["barrido_umbrales"][modo]:
            if not (fila["pasan_a_responder"] or fila["pasan_a_sin_info"]):
                continue
            clave = (fila["pasan_a_responder"], fila["pasan_a_sin_info"])
            if grupos and grupos[-1][2] == clave and abs(fila["umbral"] - grupos[-1][1] - 0.01) < 1e-9:
                grupos[-1][1] = fila["umbral"]
            else:
                grupos.append([fila["umbral"], fila["umbral"], clave])
        for desde, hasta, (a_responder, a_sin_info) in grupos:
            rango = f"{desde:.2f}" if desde == hasta else f"{desde:.2f} a {hasta:.2f}"
            lineas.append(f"| {rango} | {', '.join(a_responder) or '-'} | {', '.join(a_sin_info) or '-'} |")
        lineas.append("")
    if respuestas:
        lineas += ["## Respuesta completa", ""]
        rc = respuestas["contexto"]
        if rc.get("casos_omitidos"):
            lineas += [
                "- Casos omitidos en esta corrida: "
                + ", ".join(f"{o['id']} ({o['motivo']})" for o in rc["casos_omitidos"])
                + ".",
                "",
            ]
        lineas += [
            (
                f"- Corrida del {rc['fecha']} contra {rc['destino']}, artefacto \"{rc.get('artefacto')}\", "
                f"modos {', '.join(rc['modos'])}, tope de la corrida {rc['tope_usd']} USD, "
                f"gasto {_fmt(respuestas['gasto_total_usd'], 4)} USD."
            ),
            "",
        ]
        if respuestas.get("parcial"):
            lineas.append(f"**Corrida parcial** (motivo: {respuestas['motivo_parada']}).\n")
        for modo, r in respuestas["resumen"].items():
            lineas += [
                f"### Modo {modo}",
                "",
                (
                    f"- Consultas: {r['consultas']}; correctos: {len(r['correctos'])}; "
                    f"fallidos: {', '.join(r['fallidos']) or 'ninguno'}; "
                    f"no concluyentes: {', '.join(r['no_concluyentes']) or 'ninguno'}."
                ),
                f"- Fuentes sobrantes promedio: {_fmt(r['fuentes_sobrantes_promedio'], 2)}.",
                f"- Latencia p50 / p95: {_fmt(r['latencia_p50_ms'], 0)} ms / {_fmt(r['latencia_p95_ms'], 0)} ms.",
                (
                    f"- Costo medio por consulta: {_fmt(r['costo_medio_usd'], 6)} USD; "
                    f"el de las que terminan en \"sin información\": {_fmt(r['costo_medio_sin_info_usd'], 6)} USD."
                ),
                f"- Gasto total: {_fmt(r['gasto_total_usd'], 4)} USD.",
                *(
                    [
                        (
                            f"- Reintentos: {r['reintentos']}; avisos de posible corte: {r['avisos_de_corte']}; "
                            f"respuestas que terminan sin puntuación: {r['terminan_sin_puntuacion']} "
                            f"({_fmt(100 * r['proporcion_terminan_sin_puntuacion'], 1)} % de las que tienen contenido)."
                        )
                    ]
                    if r.get("proporcion_terminan_sin_puntuacion") is not None
                    else []
                ),
                *(
                    [
                        (
                            f"- Segundos intentos: {r['segundos_intentos']}; con resultados: "
                            f"{r['segundos_intentos_con_resultados']}; negativos reformulados: "
                            f"{', '.join(r['negativos_reformulados']) or 'ninguno'}."
                        )
                    ]
                    if r.get("segundos_intentos") or r.get("negativos_reformulados")
                    else []
                ),
                *(
                    [
                        (
                            f"- Consultas con reranker: {r['consultas_con_reranker']}; caídas a coseno: "
                            f"{r['caidas_a_coseno']}; sin candidatos sobre el mínimo: {r['ninguno_sobre_minimo']}."
                        )
                    ]
                    if r.get("consultas_con_reranker")
                    else []
                ),
                *(
                    [
                        (
                            f"- Regla de seguridad de las citas: {r['regla_de_seguridad_aplicada']} respuestas con "
                            f"contenido ({_fmt(100 * r['proporcion_regla_de_seguridad'], 1)} %)."
                        )
                    ]
                    if r.get("proporcion_regla_de_seguridad") is not None
                    else []
                ),
                "",
            ]
    return "\n".join(lineas) + "\n"


# ---------------------------------------------------------------------------
# Acceso a datos de solo lectura (puntajes e inventario)
# ---------------------------------------------------------------------------


class ClienteSoloLectura:
    """Envuelve el cliente de Qdrant y solo deja pasar las operaciones de lectura."""

    PERMITIDOS = frozenset({"query_points", "count", "get_collection", "collection_exists"})

    def __init__(self, cliente):
        self._cliente = cliente

    def __getattr__(self, nombre):
        if nombre not in self.PERMITIDOS:
            raise PermissionError(f"Operación no permitida en una medición de solo lectura: {nombre}")
        return getattr(self._cliente, nombre)


def sesion_solo_lectura(engine):
    """Sesión sobre la base de metadatos en la que cualquier escritura falla: transacción de solo
    lectura en Postgres y `PRAGMA query_only` en SQLite."""
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    conexion = engine.connect()
    if engine.dialect.name == "postgresql":
        conexion = conexion.execution_options(postgresql_readonly=True)
    elif engine.dialect.name == "sqlite":
        conexion.execute(text("PRAGMA query_only = ON"))
    return Session(bind=conexion)


def abrir_mia(env_file: str | None):
    """Prepara el acceso de solo lectura a la base de metadatos y a Qdrant. Nunca migra ni crea nada.

    No se llama a `init_db()` (migraría la base) ni a `ensure_collection()` (crea índices en Qdrant).
    """
    if env_file and not cargar_env(env_file, sobrescribir=True):
        raise ErrorMedicion(f"No se pudo leer el archivo de entorno {env_file}.")
    from mia.config import settings
    from mia.storage.db import engine
    from mia.storage.vector_store import get_vector_store

    sesion = sesion_solo_lectura(engine)
    almacen = get_vector_store()
    almacen.client = ClienteSoloLectura(almacen.client)
    return settings, sesion, almacen


def mapas_de_base(sesion):
    """(dominios por nombre `Programa / Dominio` -> id, nombre por id, nombre de archivo por documento, documentos por dominio)."""
    from sqlalchemy import select

    from mia.storage.models import Document, Domain, Unit

    unidades = {u.id: u.name for u in sesion.scalars(select(Unit))}
    por_nombre, nombre_de = {}, {}
    for d in sesion.scalars(select(Domain)):
        etiqueta = _nfc(f"{unidades.get(d.unit_id or '', '')}{SEPARADOR}{d.name}") if d.unit_id else _nfc(d.name)
        por_nombre[etiqueta] = d.id
        nombre_de[d.id] = etiqueta
    archivos, por_dominio = {}, {}
    for doc in sesion.scalars(select(Document)):
        archivos[doc.id] = doc.filename
        por_dominio.setdefault(doc.domain_id, []).append(doc.filename)
    return por_nombre, nombre_de, archivos, por_dominio


def contar_fragmentos(almacen, dominio_id: str) -> int:
    from qdrant_client.models import FieldCondition, Filter, MatchValue

    return almacen.client.count(
        collection_name=almacen.collection,
        count_filter=Filter(must=[FieldCondition(key="domain", match=MatchValue(value=dominio_id))]),
        exact=True,
    ).count


def medir_caso(pregunta, dominio_ids, embedder, almacen, archivos, nombre_de) -> list[dict]:
    """Candidatos de una pregunta, con la misma búsqueda que la API. El texto de los fragmentos se descarta."""
    vector = embedder.embed([pregunta], is_query=True)[0]
    resultados = almacen.search(vector, domains=dominio_ids, limit=CANDIDATOS)
    return [
        {
            "posicion": i,
            "puntaje": round(float(r.score), 6),
            "documento": archivos.get(r.document_id, r.document_id),
            "dominio": nombre_de.get(r.domain, r.domain),
        }
        for i, r in enumerate(resultados, start=1)
    ]


def medir_caso_rerank(pregunta_busqueda, pregunta_rerank, dominio_ids, embedder, almacen, archivos, nombre_de,
                      reranker, candidatos_pedidos: int, piso: float, reloj=time.perf_counter):
    """Candidatos de una pregunta puntuados por el reranker, como los puntúa la API: se busca con la pregunta (o la
    variante) y se puntúa contra `pregunta_rerank` (la pregunta completa). Devuelve (candidatos, milisegundos)."""
    from mia.rag.rerank import sigmoid

    vector = embedder.embed([pregunta_busqueda], is_query=True)[0]
    resultados = almacen.search(vector, domains=dominio_ids, limit=candidatos_pedidos)
    elegidos = [(i, r) for i, r in enumerate(resultados, start=1) if piso <= 0 or r.score >= piso]
    if not elegidos:
        return [], 0.0
    inicio = reloj()
    logits = reranker.score(pregunta_rerank, [r.text for _, r in elegidos])
    ms = (reloj() - inicio) * 1000
    filas = [
        {
            "posicion": i,
            "puntaje_coseno": round(float(r.score), 6),
            "logit": round(float(logit), 4),
            "puntaje": round(sigmoid(float(logit)), 6),
            "documento": archivos.get(r.document_id, r.document_id),
            "dominio": nombre_de.get(r.domain, r.domain),
        }
        for (i, r), logit in zip(elegidos, logits, strict=True)
    ]
    orden = sorted(range(len(filas)), key=lambda k: -filas[k]["logit"])
    for rango, k in enumerate(orden, start=1):
        filas[k]["posicion_rerank"] = rango
    return filas, ms


def medir_combinacion(reranker, tareas: list[tuple[str, list[str]]], repeticiones: int,
                      reloj=time.perf_counter) -> list[float]:
    """Milisegundos de cada puntuación de `tareas` (pregunta, pasajes) repetida `repeticiones` veces, después de una
    pasada de calentamiento que no se cuenta."""
    for pregunta, pasajes in tareas:
        reranker.score(pregunta, pasajes)
    medidas = []
    for _ in range(repeticiones):
        for pregunta, pasajes in tareas:
            inicio = reloj()
            reranker.score(pregunta, pasajes)
            medidas.append((reloj() - inicio) * 1000)
    return medidas


def exigir_casos(casos: list, omitidos: list) -> None:
    """Sin ningún caso que correr no se mide nada ni se escribe ningún archivo."""
    if not casos:
        motivo = "; ".join(f"{o['id']} ({o['motivo']})" for o in omitidos)
        raise ErrorMedicion("No queda ningún caso para correr" + (f": {motivo}." if motivo else " (revisar --solo)."))


def parametros_de_puntajes(etiqueta: str) -> dict | None:
    """Umbral, límites y fragmentos por dominio de la corrida de `puntajes` de la misma etiqueta (FR-014)."""
    try:
        puntajes = leer_corrida(etiqueta)["puntajes"]
    except FileNotFoundError:
        return None
    if not puntajes:
        return None
    contexto = puntajes["contexto"]
    return {
        clave: contexto.get(clave)
        for clave in ("umbral", "limite_literal", "limite_razonamiento", "fragmentos_por_dominio", "fecha")
    }


def comando_inventario(args) -> int:
    _, sesion, almacen = abrir_mia(args.env_file)
    por_nombre, _, _, docs_por_dominio = mapas_de_base(sesion)
    for etiqueta in sorted(por_nombre):
        dominio_id = por_nombre[etiqueta]
        archivos = sorted(docs_por_dominio.get(dominio_id, []))
        print(f"{etiqueta}: {len(archivos)} documentos, {contar_fragmentos(almacen, dominio_id)} fragmentos")
        for nombre in archivos:
            print(f"    {nombre}")
    return 0


def comando_puntajes(args) -> int:
    settings, sesion, almacen = abrir_mia(args.env_file)
    from mia.rag.embeddings import get_embedding_provider

    inicio = time.perf_counter()
    embedder = get_embedding_provider(settings.embedding_provider)
    dimension = len(embedder.embed(["prueba"], is_query=True)[0])
    existente = almacen.client.get_collection(almacen.collection).config.params.vectors.size
    if existente != dimension:
        raise ErrorMedicion(
            f"La colección tiene vectores de dimensión {existente} y el proveedor genera {dimension}: no se mezclan puntajes."
        )

    casos = cargar_casos(Path(args.casos))
    solo = {c.strip() for c in args.solo.split(",") if c.strip()}
    casos = [c for c in casos if not solo or c["id"] in solo]
    por_nombre, nombre_de, archivos, _ = mapas_de_base(sesion)
    limites = {"literal": settings.query_search_limit, "razonamiento": settings.query_search_limit_razonamiento}
    umbral = settings.query_similarity_threshold

    reranker = None
    minimo = settings.rerank_min_score
    if args.rerank:
        from mia.rag.rerank import get_rerank_provider

        reranker = get_rerank_provider("local")
        if reranker is None:
            raise ErrorMedicion("No se pudo cargar el reranker local (ver el registro): revisar el modelo y las dependencias.")
    candidatos_rerank = max(settings.rerank_candidates, *limites.values())

    mediciones, omitidos = [], []
    exigir_casos(casos, [])
    for caso in casos:
        faltan = [d for d in caso["dominios"] if _nfc(d) not in por_nombre]
        if faltan:
            omitidos.append({"id": caso["id"], "motivo": f"dominio inexistente: {faltan}"})
            print(f"[omitido] {caso['id']}: no existe el dominio {faltan}")
            continue
        ids = [por_nombre[_nfc(d)] for d in caso["dominios"]]
        variantes = [("completa", caso["pregunta"])]
        if caso.get("variante_corta"):
            variantes.append(("corta", caso["variante_corta"]))
        # La pregunta limpia de la feature 008, calculada con el mismo código que la API: sin costo.
        limpia = variante_limpia(caso)
        if limpia:
            variantes.append(("limpia", limpia))
        for variante, pregunta in variantes:
            candidatos = medir_caso(pregunta, ids, embedder, almacen, archivos, nombre_de)
            medicion = {
                "caso_id": caso["id"],
                "variante": variante,
                "categoria": caso["categoria"],
                "grupo": caso.get("grupo"),
                "espera": caso["espera"],
                "candidatos": candidatos,
                "por_modo": {m: resultado_por_modo(candidatos, limites[m], umbral) for m in MODOS},
                "esperados": posicion_esperados(candidatos, caso.get("documentos", [])),
            }
            if reranker is not None:
                # La API puntúa siempre contra la pregunta completa, incluso cuando busca con la variante limpia.
                pregunta_rerank = caso["pregunta"] if variante == "limpia" else pregunta
                candidatos_r, ms = medir_caso_rerank(
                    pregunta, pregunta_rerank, ids, embedder, almacen, archivos, nombre_de, reranker,
                    candidatos_rerank, settings.rerank_min_similarity,
                )
                medicion["rerank"] = {
                    "candidatos": candidatos_r,
                    "ms": round(ms, 1),
                    "por_modo": {m: resultado_por_modo_rerank(candidatos_r, limites[m], minimo) for m in MODOS},
                    "esperados": puesto_rerank(candidatos_r, caso.get("documentos", []), minimo, limites),
                }
            mediciones.append(medicion)
            esperado = ", ".join(
                f"{e['fragmento'][:18]}: " + ("ausente" if e["posicion"] is None else f"#{e['posicion']} {e['puntaje']:.3f}")
                for e in medicion["esperados"]
            )
            print(
                f"{caso['id']:<6}{variante:<9} mejor {candidatos[0]['puntaje'] if candidatos else 0:.3f} "
                f"| literal {medicion['por_modo']['literal']['resultado']} ({medicion['por_modo']['literal']['pasan']}) "
                f"| razonamiento {medicion['por_modo']['razonamiento']['resultado']} "
                f"({medicion['por_modo']['razonamiento']['pasan']}) | espera {caso['espera']}"
                + (f" | {esperado}" if esperado else "")
            )
            if "rerank" in medicion:
                rr = medicion["rerank"]
                mejor_r = max((c["puntaje"] for c in rr["candidatos"]), default=0.0)
                esperado_r = ", ".join(
                    f"{e['fragmento'][:18]}: " + ("ausente" if e["posicion_rerank"] is None else
                                                  f"#{e['posicion']}->#{e['posicion_rerank']} {e['puntaje_rerank']:.3f}")
                    for e in rr["esperados"]
                )
                print(
                    f"{'':<15}rerank mejor {mejor_r:.3f} | literal {rr['por_modo']['literal']['resultado']} "
                    f"| razonamiento {rr['por_modo']['razonamiento']['resultado']} | {rr['ms']:.0f} ms"
                    + (f" | {esperado_r}" if esperado_r else "")
                )

    exigir_casos(mediciones, omitidos)
    contexto = contexto_corrida(
        args.etiqueta,
        destino_de(settings.qdrant_url),
        umbral=umbral,
        limite_literal=limites["literal"],
        limite_razonamiento=limites["razonamiento"],
        candidatos_pedidos=CANDIDATOS,
        proveedor_embeddings=settings.embedding_provider,
        dimension=dimension,
        fragmentos_por_dominio={nombre_de[i]: contar_fragmentos(almacen, i) for i in nombre_de},
        casos_omitidos=omitidos,
        parametros="declarados en el archivo de entorno, no necesariamente los de Railway",
        **(
            {
                "reranker": {
                    "modelo": "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1 (ONNX int8)",
                    "candidatos": candidatos_rerank,
                    "minimo": minimo,
                    "piso_de_similitud": settings.rerank_min_similarity,
                    "tokens_por_pasaje": settings.rerank_passage_tokens,
                    "hilos": settings.rerank_threads,
                }
            }
            if reranker is not None
            else {}
        ),
    )
    resumen = resumen_puntajes(mediciones, umbral, limites)
    if reranker is not None:
        resumen["barrido_minimos"] = barrido_minimos(mediciones)
        resumen["ventana_rerank"] = ventana_rerank(mediciones)
    ruta = guardar_json(carpeta_de(contexto), "puntajes.json", {"contexto": contexto, "mediciones": mediciones, "resumen": resumen})
    v = resumen["ventana_separacion"]
    print(f"\nVentana de separación: sin información hasta {v['max_sin_info']}, con respuesta desde {v['min_respuesta']} -> "
          + ("separables" if v["separables"] else "NO separables por umbral"))
    if reranker is not None:
        w = resumen["ventana_rerank"]
        print(
            f"Ventana del reranker (logit): sin información hasta {_fmt(w['max_sin_info_logit'], 2)} (caso {w['max_sin_info_caso']}), "
            f"con respuesta desde {_fmt(w['min_respuesta_logit'], 2)} (caso {w['min_respuesta_caso']}) -> "
            + ("separables" if w["separables"] else "NO separables por mínimo")
            + (f"; ausentes entre los candidatos: {', '.join(w['ausentes'])}" if w["ausentes"] else "")
        )
    print(f"Duración: {time.perf_counter() - inicio:.0f} s. Guardado en {ruta.relative_to(RAIZ)}")
    return 0


def _enteros(texto: str) -> list[int]:
    return [int(x) for x in texto.split(",") if x.strip()]


def comando_rendimiento(args) -> int:
    """Memoria y latencia del reranker local por número de candidatos, tokens por pasaje e hilos (feature 009)."""
    settings, sesion, almacen = abrir_mia(args.env_file)
    from mia.rag.embeddings import get_embedding_provider
    from mia.rag.providers.local_rerank import LocalRerankProvider
    from mia.rag.rerank import format_memory, read_memory_mb

    inicio = time.perf_counter()
    embedder = get_embedding_provider(settings.embedding_provider)
    embedder.embed(["prueba"], is_query=True)
    memoria_embeddings, _ = read_memory_mb()

    casos = cargar_casos(Path(args.casos))
    por_nombre, _, _, _ = mapas_de_base(sesion)
    tareas: list[tuple[str, list[str]]] = []
    for caso in casos:
        if len(tareas) >= args.n_casos:
            break
        if any(_nfc(d) not in por_nombre for d in caso["dominios"]):
            continue
        ids = [por_nombre[_nfc(d)] for d in caso["dominios"]]
        vector = embedder.embed([caso["pregunta"]], is_query=True)[0]
        textos = [r.text for r in almacen.search(vector, domains=ids, limit=max(_enteros(args.candidatos)))]
        if textos:
            tareas.append((caso["pregunta"], textos))
    if not tareas:
        raise ErrorMedicion("No se encontraron pasajes reales para medir (revisar el archivo de entorno y los casos).")
    print(f"{len(tareas)} casos con pasajes reales; embeddings cargados ({format_memory(memoria_embeddings)} MB).")

    filas = []
    memoria = {"embeddings_mb": memoria_embeddings}
    for hilos in _enteros(args.hilos):
        settings.rerank_threads = hilos
        antes, _ = read_memory_mb()
        reranker = LocalRerankProvider()
        despues, pico = read_memory_mb()
        memoria.setdefault("reranker_cargado_mb", despues)
        memoria["pico_mb"] = pico
        if "reranker_antes_mb" not in memoria:
            memoria["reranker_antes_mb"] = antes
        for tokens in _enteros(args.tokens):
            settings.rerank_passage_tokens = tokens
            for n in _enteros(args.candidatos):
                trabajo = [(pregunta, textos[:n]) for pregunta, textos in tareas]
                medidas = medir_combinacion(reranker, trabajo, args.repeticiones)
                resumen = resumen_rendimiento(medidas, args.p50_max_ms, args.p95_max_ms)
                memoria["bajo_carga_mb"], memoria["pico_mb"] = read_memory_mb()
                filas.append({"candidatos": n, "tokens": tokens, "hilos": hilos, **resumen})
                print(
                    f"hilos {hilos} | tokens {tokens:>3} | candidatos {n:>2} | p50 {resumen['p50_ms']:.0f} ms "
                    f"| p95 {resumen['p95_ms']:.0f} ms | {'CUMPLE' if resumen['cumple'] else 'no cumple'}"
                )
        del reranker
    contexto = contexto_corrida(
        args.etiqueta, destino_de(settings.qdrant_url), casos_usados=len(tareas), repeticiones=args.repeticiones,
        limites_ms={"p50": args.p50_max_ms, "p95": args.p95_max_ms}, memoria=memoria,
    )
    ruta = guardar_json(carpeta_de(contexto), "rendimiento.json", {"contexto": contexto, "combinaciones": filas})
    cumplen = [f for f in filas if f["cumple"]]
    print(
        f"\nMemoria (MB): embeddings {format_memory(memoria['embeddings_mb'])}, con el reranker cargado "
        f"{format_memory(memoria.get('reranker_cargado_mb'))}, bajo carga {format_memory(memoria.get('bajo_carga_mb'))}, "
        f"pico {format_memory(memoria.get('pico_mb'))}."
    )
    print(f"Combinaciones que cumplen {args.p50_max_ms:.0f}/{args.p95_max_ms:.0f} ms: {len(cumplen)} de {len(filas)}.")
    print(f"Duración: {time.perf_counter() - inicio:.0f} s. Guardado en {ruta.relative_to(RAIZ)}")
    return 0


# ---------------------------------------------------------------------------
# Respuestas (HTTP)
# ---------------------------------------------------------------------------


def _pedir(url: str, clave_artefacto: str = "", clave_admin: str = "", payload: dict | None = None, timeout: int = 200):
    datos = json.dumps(payload).encode() if payload is not None else None
    cabeceras = {"content-type": "application/json"}
    if clave_artefacto:
        cabeceras["X-Artifact-Key"] = clave_artefacto
    if clave_admin:
        cabeceras["X-Admin-Key"] = clave_admin
    peticion = urllib.request.Request(url, data=datos, headers=cabeceras)
    try:
        with urllib.request.urlopen(peticion, timeout=timeout) as respuesta:
            return respuesta.status, json.load(respuesta)
    except urllib.error.HTTPError as error:
        try:
            return error.code, json.load(error)
        except json.JSONDecodeError:
            return error.code, {}


def leer_costo(base_url: str, clave_admin: str, consulta_id: str) -> dict | None:
    """Costo y tokens de una consulta, desde el módulo Uso. Descarta pregunta, respuesta y demás campos."""
    status, cuerpo = _pedir(f"{base_url}/usage/queries/{consulta_id}", clave_admin=clave_admin, timeout=60)
    if status != 200:
        return None
    return {
        "cost_usd": cuerpo.get("cost_usd"),
        "cost_estimated": cuerpo.get("cost_estimated"),
        "tokens": cuerpo.get("tokens"),
        "reject_reason": cuerpo.get("reject_reason"),
    }


def estado_artefacto(base_url: str, clave_artefacto: str, clave_admin: str) -> dict | None:
    """Gasto del día y tope del artefacto cuya clave se usa (se reconoce por el prefijo de la clave)."""
    status, cuerpo = _pedir(f"{base_url}/artifacts", clave_admin=clave_admin, timeout=60)
    if status != 200:
        return None
    for artefacto in cuerpo.get("artifacts", []):
        if clave_artefacto.startswith(artefacto["key_prefix"]):
            return artefacto
    return None


def comando_respuestas(args) -> int:
    cargar_env(RAIZ / ".env", sobrescribir=False)
    clave = args.clave or os.environ.get("MIA_ARTIFACT_KEY", "")
    admin = args.clave_admin or os.environ.get("MIA_ADMIN_KEY", "")
    if not clave:
        raise ErrorMedicion("Falta la clave del artefacto: MIA_ARTIFACT_KEY en .env o --clave.")
    if args.tope_usd is None or args.tope_usd <= 0:
        raise ErrorMedicion("--tope-usd es obligatorio y debe ser mayor que cero.")
    base = args.url.rstrip("/")
    modos = list(MODOS) if args.modo == "ambos" else [args.modo]

    status, dominios = _pedir(f"{base}/domains", clave_artefacto=clave, timeout=60)
    if status != 200:
        raise ErrorMedicion(f"No se pudo listar los dominios (HTTP {status}): ¿la API está encendida y la clave es válida?")
    por_nombre = {_nfc(f"{d.get('unit_name')}{SEPARADOR}{d['name']}"): d["id"] for d in dominios}

    solo = {c.strip() for c in args.solo.split(",") if c.strip()}
    casos, omitidos = [], []
    for caso in cargar_casos(Path(args.casos)):
        if solo and caso["id"] not in solo:
            continue
        faltan = [d for d in caso["dominios"] if _nfc(d) not in por_nombre]
        if faltan:
            omitidos.append({"id": caso["id"], "motivo": f"el artefacto no puede consultar: {faltan}"})
            print(f"[omitido] {caso['id']}: el artefacto no puede consultar {faltan}")
            continue
        casos.append(caso)

    exigir_casos(casos, omitidos)
    estado = estado_artefacto(base, clave, admin) if admin else None
    if estado:
        print(f"Artefacto '{estado['name']}': gastó hoy {estado['today']['spent_usd']:.4f} USD de {estado['daily_cap_usd']:.2f} USD de tope diario.")
        if estado["today"]["cap_reached"]:
            raise ErrorMedicion("El artefacto ya alcanzó su tope diario: no se corre nada.")
    else:
        print("Aviso: sin clave de administración no se puede leer el costo ni el tope diario del artefacto.")
    previstas = sum(len(modos) * (2 if c.get("variante_corta") else 1) for c in casos)
    print(f"Consultas previstas: {previstas} (tope de esta corrida: {args.tope_usd:.2f} USD).")

    def consultar(caso, variante, modo):
        pregunta = caso["pregunta"] if variante == "completa" else caso["variante_corta"]
        payload = {"domains": [por_nombre[_nfc(d)] for d in caso["dominios"]], "question": pregunta, "mode": modo}
        for intento in range(1, REINTENTOS + 1):
            inicio = time.perf_counter()
            status, cuerpo = _pedir(f"{base}/query", clave_artefacto=clave, payload=payload)
            ms = int((time.perf_counter() - inicio) * 1000)
            if status != 502 or intento == REINTENTOS:
                print(f"{caso['id']:<6}{variante:<9}{modo:<13} HTTP {status} {ms / 1000:.1f} s")
                return status, cuerpo, ms
            time.sleep(ESPERA_REINTENTO)
        raise AssertionError("inalcanzable")

    costo = (lambda consulta_id: leer_costo(base, admin, consulta_id)) if admin else (lambda consulta_id: None)
    corrida = correr_respuestas(casos, modos, consultar, costo, args.tope_usd)
    contexto = contexto_corrida(
        args.etiqueta, destino_de(base), modos=modos, tope_usd=args.tope_usd, casos_omitidos=omitidos,
        artefacto=estado["name"] if estado else None,
        parametros_de_puntajes=parametros_de_puntajes(args.etiqueta),
    )
    resumen = resumen_respuestas(corrida["resultados"])
    ruta = guardar_json(
        carpeta_de(contexto), "respuestas.json", {"contexto": contexto, **corrida, "resumen": resumen}
    )
    for modo, r in resumen.items():
        print(f"\n{modo}: {len(r['correctos'])} correctos, fallidos {r['fallidos'] or 'ninguno'}, "
              f"sobrantes promedio {_fmt(r['fuentes_sobrantes_promedio'], 2)}, p50 {_fmt(r['latencia_p50_ms'], 0)} ms, "
              f"costo medio {_fmt(r['costo_medio_usd'], 6)} USD")
    print(f"Gasto total: {corrida['gasto_total_usd']:.4f} USD" + (f" (parcial: {corrida['motivo_parada']})" if corrida["parcial"] else ""))
    print(f"Guardado en {ruta.relative_to(RAIZ)}")
    return 0


# ---------------------------------------------------------------------------
# Informe y comparación
# ---------------------------------------------------------------------------


def comando_informe(args) -> int:
    try:
        corrida = leer_corrida(args.etiqueta)
        texto = generar_informe(corrida)
    except (FileNotFoundError, ValueError) as error:
        print(error, file=sys.stderr)
        return 2
    if args.salida:
        destino = Path(args.salida)
        if destino.is_file():
            previo = destino.read_text(encoding="utf-8")
            if "\n## Lectura" in previo:
                # La lectura la escribe una persona: regenerar el informe no debe borrarla.
                texto = texto.rstrip("\n") + "\n" + previo[previo.index("\n## Lectura") :]
        destino.write_text(texto, encoding="utf-8")
        print(f"Informe escrito en {args.salida}")
    else:
        print(texto)
    return 0


def comando_comparar(args) -> int:
    try:
        a, b = leer_corrida(args.etiqueta_a), leer_corrida(args.etiqueta_b)
    except FileNotFoundError as error:
        print(error, file=sys.stderr)
        return 2
    resultado = comparar(a, b)
    if resultado["datos_distintos"]:
        print("AVISO: el conteo de fragmentos por dominio difiere entre las corridas: los datos no son los mismos.")
    for cambio in resultado["cambios"]:
        print(cambio)
    for modo, m in resultado["medianas"].items():
        print(
            f"Mediana de la razón {args.etiqueta_b}/{args.etiqueta_a}, modo {modo} ({m['casos']} casos con costo): "
            f"costo {_fmt(m['razon_costo'], 3)}, latencia {_fmt(m['razon_latencia'], 3)}."
        )
    print(f"{len(resultado['cambios'])} diferencias.")
    return 1 if resultado["cambios"] else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="comando", required=True)

    inv = sub.add_parser("inventario", help="Dominios, documentos y fragmentos (solo lectura)")
    inv.add_argument("--env-file", default=None, help="Archivo tipo .env con las credenciales (p. ej. .env.produccion)")
    inv.set_defaults(funcion=comando_inventario)

    pun = sub.add_parser("puntajes", help="Puntajes de similitud por caso (solo lectura, sin tokens)")
    pun.add_argument("--etiqueta", required=True)
    pun.add_argument("--env-file", default=None)
    pun.add_argument("--solo", default="", help="Ids de casos separados por coma")
    pun.add_argument("--casos", default=str(RUTA_CASOS), help="Archivo de casos (por defecto el versionado)")
    pun.add_argument("--rerank", action="store_true", help="Puntúa también con el reranker local (feature 009)")
    pun.set_defaults(funcion=comando_puntajes)

    ren = sub.add_parser("rendimiento", help="Memoria y latencia del reranker local (solo lectura, sin tokens)")
    ren.add_argument("--etiqueta", required=True)
    ren.add_argument("--env-file", default=None)
    ren.add_argument("--casos", default=str(RUTA_CASOS), help="Archivo de casos (por defecto el versionado)")
    ren.add_argument("--n-casos", type=int, default=4, help="Cuántos casos con pasajes reales se usan")
    ren.add_argument("--candidatos", default="10,20,30", help="Números de candidatos separados por coma")
    ren.add_argument("--tokens", default="128,192,256", help="Tokens por pasaje separados por coma")
    ren.add_argument("--hilos", default="1,2,4", help="Hilos de cálculo separados por coma")
    ren.add_argument("--repeticiones", type=int, default=2)
    ren.add_argument("--p50-max-ms", type=float, default=500, help="Límite de p50 (SC-006)")
    ren.add_argument("--p95-max-ms", type=float, default=1500, help="Límite de p95 (SC-006)")
    ren.set_defaults(funcion=comando_rendimiento)

    res = sub.add_parser("respuestas", help="Respuesta completa contra POST /query (gasta; exige --tope-usd)")
    res.add_argument("--etiqueta", required=True)
    res.add_argument("--url", required=True, help="URL base de la API, sin barra final")
    res.add_argument("--clave", default="", help="Clave del artefacto (o MIA_ARTIFACT_KEY en .env)")
    res.add_argument("--clave-admin", default="", help="Clave de administración (o MIA_ADMIN_KEY en .env)")
    res.add_argument("--tope-usd", type=float, default=None, help="Gasto máximo de la corrida (obligatorio)")
    res.add_argument("--modo", default="ambos", choices=["literal", "razonamiento", "ambos"])
    res.add_argument("--solo", default="")
    res.add_argument("--casos", default=str(RUTA_CASOS), help="Archivo de casos (por defecto el versionado)")
    res.set_defaults(funcion=comando_respuestas)

    inf = sub.add_parser("informe", help="Informe en Markdown de una corrida")
    inf.add_argument("etiqueta")
    inf.add_argument("--salida", default=None)
    inf.set_defaults(funcion=comando_informe)

    comp = sub.add_parser("comparar", help="Compara dos corridas caso por caso")
    comp.add_argument("etiqueta_a")
    comp.add_argument("etiqueta_b")
    comp.set_defaults(funcion=comando_comparar)

    args = parser.parse_args(argv)
    try:
        return args.funcion(args)
    except ErrorMedicion as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
