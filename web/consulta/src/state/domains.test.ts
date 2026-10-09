import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Domain } from "../api/types";
import { groupByUnit, loadSelection, restoreSelection, saveSelection } from "./domains";

const domain = (id: string, name: string, unit: string | null): Domain => ({
  id,
  name,
  unit_id: unit ? `u-${unit}` : null,
  unit_name: unit,
  description: "",
});

const a = domain("a", "Currículum", "Computación");
const b = domain("b", "Memoria del Consejo", "Computación");
const c = domain("c", "Currículum", "Administración de Empresas");

describe("groupByUnit", () => {
  it("con una sola unidad devuelve un grupo sin título", () => {
    expect(groupByUnit([b, a])).toEqual([{ title: null, domains: [a, b] }]);
  });

  it("con varias unidades agrupa por nombre de unidad en orden alfabético", () => {
    expect(groupByUnit([b, c, a])).toEqual([
      { title: "Administración de Empresas", domains: [c] },
      { title: "Computación", domains: [a, b] },
    ]);
  });

  it("los dominios sin unidad van en un grupo aparte al final", () => {
    const sinUnidad = domain("d", "Suelto", null);
    expect(groupByUnit([sinUnidad, a, c]).map((g) => g.title)).toEqual([
      "Administración de Empresas",
      "Computación",
      "Otros",
    ]);
  });

  it("sin dominios no hay grupos", () => {
    expect(groupByUnit([])).toEqual([]);
  });
});

describe("restoreSelection", () => {
  it("sin nada guardado selecciona todos", () => {
    expect(restoreSelection([], [a, b])).toEqual(["a", "b"]);
  });

  it("si ninguno de los guardados sigue permitido selecciona todos", () => {
    expect(restoreSelection(["x", "y"], [a, b])).toEqual(["a", "b"]);
  });

  it("conserva solo los guardados que siguen permitidos", () => {
    expect(restoreSelection(["b", "x"], [a, b])).toEqual(["b"]);
  });

  it("sin dominios permitidos no selecciona nada", () => {
    expect(restoreSelection(["a"], [])).toEqual([]);
  });
});

// Vitest corre en Node, sin localStorage: se simula uno en memoria.
function fakeStorage() {
  const data = new Map<string, string>();
  return {
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => void data.set(key, value),
    removeItem: (key: string) => void data.delete(key),
  };
}

describe("loadSelection y saveSelection", () => {
  beforeEach(() => vi.stubGlobal("localStorage", fakeStorage()));
  afterEach(() => vi.unstubAllGlobals());

  it("guardan y leen la lista de ids", () => {
    saveSelection(["a", "b"]);
    expect(loadSelection()).toEqual(["a", "b"]);
  });

  it("una lista vacía guardada se lee como vacía", () => {
    saveSelection([]);
    expect(loadSelection()).toEqual([]);
  });

  it("un valor dañado se lee como vacío", () => {
    localStorage.setItem("mia-consulta-dominios", "{no es json");
    expect(loadSelection()).toEqual([]);
  });

  it("sin almacenamiento no falla", () => {
    vi.stubGlobal("localStorage", {
      getItem: () => {
        throw new Error("bloqueado");
      },
      setItem: () => {
        throw new Error("bloqueado");
      },
    });
    expect(loadSelection()).toEqual([]);
    expect(() => saveSelection(["a"])).not.toThrow();
  });
});
