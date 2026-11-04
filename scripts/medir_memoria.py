"""Mide la memoria de conversación (feature 014) con documentos reales en un Qdrant local.

Ingiere los .txt de una carpeta en una colección temporal (con el mismo modelo de embeddings de producción), recorre los casos
de `scripts/datos/casos_memoria.json` y para cada caso con seguimiento mide, con cada estrategia de reformulación (`off`,
`rules` y `model`), si algún fragmento de los mejores (con el umbral de similitud de la API) es de un documento esperado.
Informa por estrategia los aciertos, el costo y el tiempo, los falsos seguimientos (un cambio de tema que se reformuló con el
historial y dejó de encontrar el documento del tema nuevo) y los seguimientos que `is_followup` no reconoció.

La estrategia `model` y las opciones `--respuestas` y `--costo-real` llaman al modelo real (cuestan centavos) y necesitan la
clave de OpenRouter del `.env`; con `--sin-modelo` no se llama a ninguno. Esta medición no usa la búsqueda híbrida ni el
reranker: compara solo cómo cambia la búsqueda por significado con la reformulación.

Sale con código 1 si la estrategia elegida (`--estrategia`, por defecto la de `HISTORY_REFORMULATION`) queda bajo el 80 % en
`tema_anterior` y `pronombre` (SC-001) o si hay algún falso seguimiento en `cambio_de_tema`.

    python scripts/medir_memoria.py --documentos tmp/nuevos --sin-modelo
    python scripts/medir_memoria.py --documentos tmp/nuevos --respuestas --costo
"""

import argparse
import json
import re
import sys
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from mia.config import settings
from mia.rag.followup import is_followup, search_question, strategy
from mia.rag.history import HistoryTurn, sanitize_history

RUTA_CASOS = RAIZ / "scripts" / "datos" / "casos_memoria.json"
ESTRATEGIAS = ("off", "rules", "model")
MINIMO_ACIERTOS = 0.8  # SC-001
CATEGORIAS_DE_SEGUIMIENTO = ("tema_anterior", "pronombre")
CARACTERES_POR_TOKEN = 3.5  # estimación gruesa para el texto en español


def cargar_casos(ruta: Path = RUTA_CASOS) -> list[dict]:
    return json.loads(ruta.read_text(encoding="utf-8"))


def historial_del_caso(caso: dict, modo: str | None = None) -> list[HistoryTurn]:
    """El historial del caso tal como lo deja la API (recortado por modo): lo que vería la búsqueda y el modelo."""
    vueltas = [HistoryTurn(t["question"], t["answer"], t.get("mode")) for t in caso["historial"]]
    return sanitize_history(vueltas, 10, modo or caso["modo"])


def acierta(resultados: list, documentos: list[str], umbral: float, limite: int) -> bool:
    """Si alguno de los `limite` mejores fragmentos que pasan el umbral es de un documento esperado (se compara por el nombre
    del archivo sin extensión)."""
    esperados = {Path(d).stem for d in documentos}
    return any(r.document_id in esperados for r in resultados[:limite] if r.score >= umbral)


@dataclass
class Medicion:
    """El resultado de un caso con una estrategia."""

    caso: dict
    estrategia: str
    acierto: bool
    reformulada: bool  # la búsqueda no usó la pregunta tal cual
    seguimiento: bool  # `is_followup` la reconoció como seguimiento
    costo_usd: float = 0.0
    segundos: float = 0.0
    texto: str = ""


def medir_caso(caso: dict, estrategia: str, buscar, umbral: float, limite: int) -> Medicion:
    """Mide un caso: reformula con la estrategia, busca (`buscar(texto)` devuelve los resultados del almacén) y comprueba."""
    historial = historial_del_caso(caso)
    inicio = time.perf_counter()
    reformulacion = search_question(caso["pregunta"], historial, estrategia)
    resultados = buscar(reformulacion.text)
    return Medicion(
        caso=caso,
        estrategia=estrategia,
        acierto=acierta(resultados, caso["documentos"], umbral, limite),
        reformulada=reformulacion.used != "none",
        seguimiento=is_followup(caso["pregunta"], historial),
        costo_usd=reformulacion.cost_usd,
        segundos=time.perf_counter() - inicio,
        texto=reformulacion.text,
    )


@dataclass
class Resumen:
    estrategia: str
    casos: int = 0
    aciertos: int = 0
    por_categoria: dict = field(
        default_factory=lambda: defaultdict(lambda: [0, 0])
    )  # categoría: [aciertos, casos]
    falsos_seguimientos: list = field(default_factory=list)
    no_reconocidos: list = field(default_factory=list)
    costo_usd: float = 0.0
    segundos: float = 0.0

    def tasa(self, categorias: tuple[str, ...]) -> float:
        aciertos = sum(self.por_categoria[c][0] for c in categorias)
        total = sum(self.por_categoria[c][1] for c in categorias)
        return aciertos / total if total else 1.0


def resumir(estrategia: str, mediciones: list[Medicion]) -> Resumen:
    resumen = Resumen(estrategia)
    for m in mediciones:
        categoria = m.caso["categoria"]
        if categoria == "calculo_en_razonamiento":
            continue  # solo se mide con --respuestas: no tiene documentos esperados
        resumen.casos += 1
        resumen.aciertos += m.acierto
        resumen.por_categoria[categoria][0] += m.acierto
        resumen.por_categoria[categoria][1] += 1
        resumen.costo_usd += m.costo_usd
        resumen.segundos += m.segundos
        if categoria == "cambio_de_tema" and m.reformulada and not m.acierto:
            resumen.falsos_seguimientos.append(m.caso["id"])
        if categoria in CATEGORIAS_DE_SEGUIMIENTO and not m.seguimiento:
            resumen.no_reconocidos.append(m.caso["id"])
    return resumen


def veredicto(resumen: Resumen) -> list[str]:
    """Los motivos por los que la estrategia no cumple (vacío si cumple)."""
    problemas = []
    tasa = resumen.tasa(CATEGORIAS_DE_SEGUIMIENTO)
    if tasa < MINIMO_ACIERTOS:
        problemas.append(
            f"aciertos en tema_anterior y pronombre: {tasa:.0%} (mínimo {MINIMO_ACIERTOS:.0%})"
        )
    if resumen.falsos_seguimientos:
        problemas.append(
            "falsos seguimientos en cambio_de_tema: " + ", ".join(resumen.falsos_seguimientos)
        )
    return problemas


def contiene_valor(texto: str, valor: str) -> bool:
    """Si la respuesta repite el valor calculado como número o palabra completa (no como parte de otro número)."""
    return re.search(rf"(?<![\w.,]){re.escape(valor)}(?![\w]|[.,]\d)", texto) is not None


def aumento_de_entrada(caso: dict, contexto: str, turnos: int) -> tuple[int, int]:
    """Caracteres y tokens estimados de más que agrega recordar `turnos` vueltas al mensaje de usuario del caso."""
    from mia.rag.llm import build_user_message

    vueltas = [HistoryTurn(t["question"], t["answer"], t.get("mode")) for t in caso["historial"]]
    historial = sanitize_history(vueltas, turnos, caso["modo"])
    base = len(build_user_message(caso["pregunta"], contexto))
    con = len(build_user_message(caso["pregunta"], contexto, historial))
    return con - base, round((con - base) / CARACTERES_POR_TOKEN)


# --- Ejecución contra un Qdrant local y, si se pide, el modelo real ---------------------------------------------------


def _imprimir(resumen: Resumen) -> None:
    categorias = ", ".join(f"{c} {a}/{n}" for c, (a, n) in sorted(resumen.por_categoria.items()))
    print(f"{resumen.estrategia:6s} aciertos {resumen.aciertos}/{resumen.casos} ({categorias})")
    print(
        f"       costo extra {resumen.costo_usd:.6f} USD ({resumen.costo_usd / max(resumen.casos, 1):.6f} por caso), "
        f"tiempo {resumen.segundos:.1f} s ({resumen.segundos / max(resumen.casos, 1):.2f} s por caso)"
    )
    print(f"       falsos seguimientos: {', '.join(resumen.falsos_seguimientos) or 'ninguno'}")
    print(f"       seguimientos no reconocidos: {', '.join(resumen.no_reconocidos) or 'ninguno'}")


def _contexto(almacen, embeddings, texto: str, limite: int) -> tuple[str, list]:
    from mia.rag.llm import RagContext, format_context

    vector = embeddings.embed([texto], is_query=True)[0]
    resultados = [
        r
        for r in almacen.search(vector, domains=["d"], limit=limite)
        if r.score >= settings.query_similarity_threshold
    ]
    piezas = [RagContext(domain="d", document=r.document_id, excerpt=r.text) for r in resultados]
    return format_context(piezas), piezas


def _respuestas(casos: list[dict], almacen, embeddings, limite: int) -> int:
    """Llama al modelo real de cada modo con los casos de cálculo: la respuesta literal no debe repetir el valor calculado."""
    from mia.rag.llm import RAG_SYSTEM_PROMPT, get_llm_provider
    from mia.rag.modes import LITERAL, mode_config

    config = mode_config(LITERAL)
    proveedor = get_llm_provider(config.provider, config.model, config.reasoning_effort)
    fallos = 0
    print("\nRespuestas (modelo real, modo literal) a los casos de cálculo en razonamiento:")
    for caso in (c for c in casos if c["categoria"] == "calculo_en_razonamiento"):
        historial = historial_del_caso(caso, LITERAL)
        busqueda = search_question(caso["pregunta"], historial).text
        _, piezas = _contexto(almacen, embeddings, busqueda, limite)
        respuesta = proveedor.answer(
            caso["pregunta"], piezas, instructions=RAG_SYSTEM_PROMPT, history=historial
        )
        repite = contiene_valor(respuesta.text, caso["no_debe_contener"])
        fallos += repite
        print(
            f"{'MAL' if repite else 'ok '} {caso['id']} costo {respuesta.cost_usd or 0:.6f} USD: {respuesta.text[:160]!r}"
        )
    return fallos


def _costo(casos: list[dict], almacen, embeddings, limite: int, memoria: int, real: bool) -> None:
    """El aumento del texto de entrada con memoria 0 y con `memoria` vueltas y, con `real`, el costo por consulta."""
    print(f"\nCosto de la memoria (series de seguimiento, memoria 0 contra {memoria}):")
    series = [c for c in casos if c["categoria"] in CATEGORIAS_DE_SEGUIMIENTO + ("cambio_de_modo",)]
    caracteres = tokens = 0
    for caso in series:
        contexto, _ = _contexto(
            almacen,
            embeddings,
            search_question(caso["pregunta"], historial_del_caso(caso)).text,
            limite,
        )
        c, t = aumento_de_entrada(caso, contexto, memoria)
        caracteres += c
        tokens += t
    n = max(len(series), 1)
    print(
        f"  texto de entrada de más por consulta: {caracteres / n:.0f} caracteres, unos {tokens / n:.0f} tokens estimados"
    )
    if not real:
        return
    from mia.rag.llm import RAG_SYSTEM_PROMPT, get_llm_provider
    from mia.rag.modes import LITERAL, mode_config

    config = mode_config(LITERAL)
    proveedor = get_llm_provider(config.provider, config.model, config.reasoning_effort)
    for turnos in (0, memoria):
        total = 0.0
        for caso in series:
            historial = historial_del_caso(caso, LITERAL)[-turnos:] if turnos else []
            busqueda = search_question(caso["pregunta"], historial).text
            _, piezas = _contexto(almacen, embeddings, busqueda, limite)
            total += (
                proveedor.answer(
                    caso["pregunta"],
                    piezas,
                    instructions=RAG_SYSTEM_PROMPT,
                    history=historial or None,
                ).cost_usd
                or 0
            )
        print(
            f"  memoria {turnos}: {total / n:.6f} USD por consulta ({len(series)} consultas, {total:.6f} USD)"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--documentos", required=True, help="carpeta con los .txt de los programas")
    parser.add_argument(
        "--qdrant", default="http://localhost:6333", help="Qdrant local (colección temporal)"
    )
    parser.add_argument(
        "--estrategia",
        choices=ESTRATEGIAS,
        default=None,
        help="la que se juzga (por defecto HISTORY_REFORMULATION)",
    )
    parser.add_argument(
        "--sin-modelo",
        action="store_true",
        help="no llamar a ningún modelo (omite `model`, --respuestas y --costo-real)",
    )
    parser.add_argument(
        "--respuestas",
        action="store_true",
        help="llama al modelo real con los casos de cálculo (cuesta centavos)",
    )
    parser.add_argument(
        "--costo",
        action="store_true",
        help="aumento del texto de entrada con memoria 0 y con --memoria vueltas",
    )
    parser.add_argument(
        "--costo-real",
        action="store_true",
        help="con --costo, el costo real por consulta con el modelo (cuesta centavos)",
    )
    parser.add_argument(
        "--memoria", type=int, default=4, help="vueltas de memoria para --costo (por defecto 4)"
    )
    args = parser.parse_args()

    from qdrant_client import QdrantClient

    from mia.ingestion.chunker import chunk_text
    from mia.rag.embeddings import get_embedding_provider
    from mia.storage.vector_store import Chunk, QdrantVectorStore

    casos = cargar_casos()
    archivos = sorted(Path(args.documentos).glob("*.txt"))
    if not archivos:
        print(f"No hay .txt en {args.documentos}", file=sys.stderr)
        return 2
    usa_modelo = not args.sin_modelo
    embeddings = get_embedding_provider(settings.embedding_provider)
    coleccion = "mia_memoria_" + uuid.uuid4().hex[:6]
    almacen = QdrantVectorStore(url=args.qdrant, collection=coleccion)
    almacen.ensure_collection(embeddings.dimension)
    limite = settings.query_search_limit
    umbral = settings.query_similarity_threshold
    elegida = args.estrategia or strategy()
    salida = 0
    try:
        for archivo in archivos:
            trozos = chunk_text(archivo.read_text(encoding="utf-8"))
            vectores = embeddings.embed(trozos, is_query=False)
            almacen.upsert(
                [
                    Chunk(
                        id=str(uuid.uuid4()),
                        document_id=archivo.stem,
                        domain="d",
                        text=t,
                        chunk_index=i,
                        embedding=v,
                    )
                    for i, (t, v) in enumerate(zip(trozos, vectores, strict=True))
                ]
            )

        def buscar(texto: str) -> list:
            return almacen.search(
                embeddings.embed([texto], is_query=True)[0], domains=["d"], limit=limite
            )

        print(
            f"{len(archivos)} documentos; umbral {umbral}, {limite} resultados; estrategia juzgada: {elegida}\n"
        )
        resumenes = {}
        for estrategia in ESTRATEGIAS:
            if estrategia == "model" and not usa_modelo:
                print("model  omitida (--sin-modelo)")
                continue
            resumenes[estrategia] = resumir(
                estrategia, [medir_caso(c, estrategia, buscar, umbral, limite) for c in casos]
            )
            _imprimir(resumenes[estrategia])
        if elegida in resumenes:
            problemas = veredicto(resumenes[elegida])
            print(
                "\n"
                + (
                    f"La estrategia {elegida} cumple."
                    if not problemas
                    else f"La estrategia {elegida} NO cumple: " + "; ".join(problemas)
                )
            )
            salida = 1 if problemas else 0
        if args.respuestas and usa_modelo:
            salida = 1 if _respuestas(casos, almacen, embeddings, limite) else salida
        if args.costo:
            _costo(casos, almacen, embeddings, limite, args.memoria, args.costo_real and usa_modelo)
    finally:
        QdrantClient(url=args.qdrant).delete_collection(coleccion)
    return salida


if __name__ == "__main__":
    sys.exit(main())
