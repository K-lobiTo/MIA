import { describe, expect, it, vi } from "vitest";
import type { DocumentItem } from "../../api/types";
import {
  alternar,
  aEliminar,
  avisoFinal,
  confirmar,
  ejecutar,
  etiquetaDeConfirmar,
  estadoDeGrupo,
  hayEnProceso,
  idsRetirados,
  marcarGrupo,
  mensajeDeMotivo,
  recortarNombres,
  sesionInicial,
  sinEliminados,
  sumarImagenes,
  textoBoton,
  textoDeResto,
  textoImagenes,
  tituloConfirmacion,
  type DocumentoAEliminar,
} from "./seleccion";

const doc = (id: string, extra: Partial<DocumentoAEliminar> = {}): DocumentoAEliminar => ({
  id,
  filename: `${id}.pdf`,
  status: "done",
  image_count: 0,
  domain_id: "d1",
  domain_name: "Admisión",
  ...extra,
});

describe("armado", () => {
  it("toma el dominio del contexto del árbol", () => {
    const item: DocumentItem = {
      id: "a",
      filename: "a.pdf",
      source_type: "pdf",
      status: "pending",
      uploaded_at: "2026-10-26T00:00:00Z",
      folder_id: null,
      image_count: 2,
    };
    expect(aEliminar(item, "d9", "Costos")).toEqual({
      id: "a",
      filename: "a.pdf",
      status: "pending",
      image_count: 2,
      domain_id: "d9",
      domain_name: "Costos",
    });
  });
});

describe("selección", () => {
  it("alterna un documento sin modificar el conjunto original", () => {
    const base = new Set(["a"]);
    expect([...alternar(base, "b")].sort()).toEqual(["a", "b"]);
    expect([...alternar(base, "a")]).toEqual([]);
    expect([...base]).toEqual(["a"]);
  });

  it("marca un grupo y, si ya estaba todo marcado, lo desmarca", () => {
    const marcado = marcarGrupo(new Set(["x"]), ["a", "b"]);
    expect([...marcado].sort()).toEqual(["a", "b", "x"]);
    expect([...marcarGrupo(marcado, ["a", "b"])]).toEqual(["x"]);
    expect([...marcarGrupo(new Set(["a"]), ["a", "b"])].sort()).toEqual(["a", "b"]);
    expect([...marcarGrupo(new Set(), [])]).toEqual([]);
  });

  it("informa el estado de la casilla de un grupo", () => {
    expect(estadoDeGrupo(new Set(), ["a", "b"])).toBe("ninguno");
    expect(estadoDeGrupo(new Set(["a"]), ["a", "b"])).toBe("algunos");
    expect(estadoDeGrupo(new Set(["a", "b"]), ["a", "b"])).toBe("todos");
    expect(estadoDeGrupo(new Set(["a"]), [])).toBe("ninguno");
  });

  it("quita de la selección los eliminados", () => {
    expect([...sinEliminados(new Set(["a", "b", "c"]), ["b", "z"])].sort()).toEqual(["a", "c"]);
  });
});

describe("textos de la confirmación", () => {
  it("recorta la lista de nombres a 10 con `y N más`", () => {
    const quince = Array.from({ length: 15 }, (_, i) => `n${i}`);
    const { visibles, resto } = recortarNombres(quince);
    expect(visibles).toHaveLength(10);
    expect(resto).toBe(5);
    expect(textoDeResto(resto)).toBe("y 5 más");
    expect(recortarNombres(["a", "b"])).toEqual({ visibles: ["a", "b"], resto: 0 });
  });

  it("suma las imágenes y las nombra en singular o plural, u omite el aviso", () => {
    expect(sumarImagenes([doc("a", { image_count: 2 }), doc("b", { image_count: 1 }), doc("c")])).toBe(3);
    expect(textoImagenes(0)).toBeNull();
    expect(textoImagenes(1)).toBe("Se pierde también 1 imagen asociada.");
    expect(textoImagenes(3)).toBe("Se pierden también 3 imágenes asociadas.");
  });

  it("arma el título y el botón según la cantidad", () => {
    expect(tituloConfirmacion(1)).toBe("Eliminar documento");
    expect(tituloConfirmacion(3)).toBe("Eliminar 3 documentos");
    expect(textoBoton(1)).toBe("Eliminar");
    expect(textoBoton(3)).toBe("Eliminar 3 documentos");
  });

  it("detecta documentos en cola o procesándose", () => {
    expect(hayEnProceso([doc("a"), doc("b", { status: "pending" })])).toBe(true);
    expect(hayEnProceso([doc("a", { status: "processing" })])).toBe(true);
    expect(hayEnProceso([doc("a"), doc("b", { status: "error" })])).toBe(false);
  });

  it("explica cada motivo de fallo en lenguaje claro", () => {
    expect(mensajeDeMotivo("out_of_scope")).toContain("fuera de tus programas");
    expect(mensajeDeMotivo("busy")).toContain("intenta de nuevo");
    expect(mensajeDeMotivo("error")).toContain("sigue como estaba");
    expect(mensajeDeMotivo("otro", "Algo raro")).toBe("Algo raro");
    expect(mensajeDeMotivo("otro")).toBe("No se pudo eliminar.");
  });
});

describe("ejecutar", () => {
  it("con un documento llama a la ruta por documento y lo da por eliminado", async () => {
    const uno = vi.fn().mockResolvedValue(undefined);
    const lote = vi.fn();
    const resultado = await ejecutar([doc("a")], { uno, lote });
    expect(uno).toHaveBeenCalledWith(doc("a"));
    expect(lote).not.toHaveBeenCalled();
    expect(resultado.eliminados.map((d) => d.id)).toEqual(["a"]);
    expect(resultado.fallidos).toEqual([]);
  });

  it("un 404 cuenta como eliminado (ya no existía) y no como fallo", async () => {
    const uno = vi.fn().mockRejectedValue({ status: 404, message: "Documento no encontrado." });
    const resultado = await ejecutar([doc("a")], { uno, lote: vi.fn() });
    expect(resultado.yaNoExistian.map((d) => d.id)).toEqual(["a"]);
    expect(resultado.fallidos).toEqual([]);
    expect(avisoFinal(resultado)).toBe("Documento eliminado (1 ya no existía).");
  });

  it.each([
    [403, "out_of_scope"],
    [409, "busy"],
    [503, "error"],
    [500, "otro"],
  ])("un %i queda como fallo con el motivo %s", async (status, motivo) => {
    const uno = vi.fn().mockRejectedValue({ status, message: "detalle" });
    const resultado = await ejecutar([doc("a")], { uno, lote: vi.fn() });
    expect(resultado.fallidos).toHaveLength(1);
    expect(resultado.fallidos[0].motivo).toBe(motivo);
    expect(resultado.eliminados).toEqual([]);
  });

  it("con varios llama al lote con los ids y ordena el resultado por documento", async () => {
    const lote = vi.fn().mockResolvedValue({
      deleted: 1,
      failed: 2,
      results: [
        { document_id: "a", status: "deleted" },
        { document_id: "b", status: "not_found" },
        { document_id: "c", status: "out_of_scope", detail: "Eso queda fuera." },
        { document_id: "d", status: "busy" },
        { document_id: "zzz", status: "deleted" },
      ],
    });
    const uno = vi.fn();
    const resultado = await ejecutar([doc("a"), doc("b"), doc("c"), doc("d")], { uno, lote });
    expect(lote).toHaveBeenCalledWith(["a", "b", "c", "d"]);
    expect(uno).not.toHaveBeenCalled();
    expect(resultado.eliminados.map((d) => d.id)).toEqual(["a"]);
    expect(resultado.yaNoExistian.map((d) => d.id)).toEqual(["b"]);
    expect(resultado.fallidos.map((f) => [f.documento.id, f.motivo])).toEqual([
      ["c", "out_of_scope"],
      ["d", "busy"],
    ]);
    expect(idsRetirados(resultado)).toEqual(["a", "b"]);
    expect(avisoFinal(resultado)).toBe("2 documentos eliminados (1 ya no existía).");
  });

  it("un error de la petición completa del lote se propaga y no da nada por eliminado", async () => {
    const lote = vi.fn().mockRejectedValue(new Error("sin conexión"));
    await expect(ejecutar([doc("a"), doc("b")], { uno: vi.fn(), lote })).rejects.toThrow("sin conexión");
  });
});

describe("aviso final", () => {
  it("singular, plural y con varios que ya no existían", () => {
    expect(avisoFinal({ eliminados: [doc("a")], yaNoExistian: [], fallidos: [] })).toBe("Documento eliminado");
    expect(avisoFinal({ eliminados: [doc("a"), doc("b")], yaNoExistian: [], fallidos: [] })).toBe("2 documentos eliminados");
    expect(avisoFinal({ eliminados: [doc("a")], yaNoExistian: [doc("b"), doc("c")], fallidos: [] })).toBe(
      "3 documentos eliminados (2 ya no existían).",
    );
  });
});

describe("sesión de la ventana de eliminación", () => {
  const exito = () => vi.fn().mockResolvedValue(undefined);

  it("al abrir (y al cancelar o cerrar, que no pasan por `confirmar`) no se llama a la API", () => {
    const api = { uno: exito(), lote: vi.fn() };
    const sesion = sesionInicial([doc("a"), doc("b")]);
    expect(sesion.pendientes.map((d) => d.id)).toEqual(["a", "b"]);
    expect(etiquetaDeConfirmar(sesion)).toBe("Eliminar 2 documentos");
    expect(etiquetaDeConfirmar(sesionInicial([doc("a")]))).toBe("Eliminar");
    expect(api.uno).not.toHaveBeenCalled();
    expect(api.lote).not.toHaveBeenCalled();
  });

  it("confirmar con un documento usa la ruta por documento y con varios la de lote", async () => {
    const uno = exito();
    const lote = vi.fn().mockResolvedValue({
      deleted: 2,
      failed: 0,
      results: [
        { document_id: "a", status: "deleted" },
        { document_id: "b", status: "deleted" },
      ],
    });
    const solo = await confirmar(sesionInicial([doc("a")]), { uno, lote });
    expect(uno).toHaveBeenCalledTimes(1);
    expect(lote).not.toHaveBeenCalled();
    expect(solo.terminado).toBe(true);

    const varios = await confirmar(sesionInicial([doc("a"), doc("b")]), { uno, lote });
    expect(lote).toHaveBeenCalledWith(["a", "b"]);
    expect(uno).toHaveBeenCalledTimes(1);
    expect(varios.terminado).toBe(true);
    expect(varios.resultado?.eliminados.map((d) => d.id)).toEqual(["a", "b"]);
  });

  it("con fallos parciales queda pendiente solo lo fallido y el botón pasa a Reintentar", async () => {
    const lote = vi.fn().mockResolvedValue({
      deleted: 1,
      failed: 2,
      results: [
        { document_id: "a", status: "deleted" },
        { document_id: "b", status: "busy" },
        { document_id: "c", status: "error" },
      ],
    });
    const avance = await confirmar(sesionInicial([doc("a"), doc("b"), doc("c")]), { uno: exito(), lote });
    expect(avance.terminado).toBe(false);
    expect(avance.sesion.pendientes.map((d) => d.id)).toEqual(["b", "c"]);
    expect(avance.sesion.fallidos.map((f) => f.motivo)).toEqual(["busy", "error"]);
    expect(etiquetaDeConfirmar(avance.sesion)).toBe("Reintentar");
  });

  it("el reintento reenvía solo los fallidos: con uno usa la ruta por documento, y si sale bien termina", async () => {
    const lote = vi.fn().mockResolvedValue({
      deleted: 1,
      failed: 1,
      results: [
        { document_id: "a", status: "deleted" },
        { document_id: "b", status: "busy" },
      ],
    });
    const uno = exito();
    const primero = await confirmar(sesionInicial([doc("a"), doc("b")]), { uno, lote });

    const segundo = await confirmar(primero.sesion, { uno, lote });

    expect(lote).toHaveBeenCalledTimes(1);
    expect(uno).toHaveBeenCalledWith(doc("b"));
    expect(segundo.terminado).toBe(true);
  });

  it("un error de la petición completa deja todo pendiente, con el mensaje y para reintentar", async () => {
    const lote = vi.fn().mockRejectedValue(new Error("sin conexión"));
    const inicial = sesionInicial([doc("a"), doc("b")]);

    const avance = await confirmar(inicial, { uno: exito(), lote });

    expect(avance.resultado).toBeNull();
    expect(avance.terminado).toBe(false);
    expect(avance.sesion.pendientes).toEqual(inicial.pendientes);
    expect(avance.sesion.error).toBe("sin conexión");
    expect(etiquetaDeConfirmar(avance.sesion)).toBe("Reintentar");
  });
});
