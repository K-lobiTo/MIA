import { describe, expect, it } from "vitest";
import type { UnitNode } from "../../api/types";
import { describeAccess, describeCost, describeModes, pruneCoveredDomains } from "./accessUtils";

const units: UnitNode[] = [
  {
    id: "u1",
    name: "Computación",
    description: "",
    document_count: 0,
    domains: [
      { id: "d1", name: "Currículum", description: "", document_count: 0, folders: [], documents: [] },
      { id: "d2", name: "Docentes", description: "", document_count: 0, folders: [], documents: [] },
    ],
  },
  {
    id: "u2",
    name: "Administración de Empresas",
    description: "",
    document_count: 0,
    domains: [{ id: "d3", name: "Currículum", description: "", document_count: 0, folders: [], documents: [] }],
  },
];

describe("describeAccess", () => {
  it("todos los dominios", () => {
    expect(describeAccess({ all_domains: true, unit_ids: [], domain_ids: [] }, units)).toMatch(/Todos los dominios/);
  });

  it("una unidad completa", () => {
    expect(describeAccess({ all_domains: false, unit_ids: ["u1"], domain_ids: [] }, units)).toBe(
      "Unidad Computación completa",
    );
  });

  it("dominios puntuales con su unidad, para distinguir los que se llaman igual", () => {
    expect(describeAccess({ all_domains: false, unit_ids: [], domain_ids: ["d1", "d3"] }, units)).toBe(
      "Computación / Currículum; Administración de Empresas / Currículum",
    );
  });

  it("unidades y dominios combinados", () => {
    expect(describeAccess({ all_domains: false, unit_ids: ["u1"], domain_ids: ["d3"] }, units)).toBe(
      "Unidad Computación completa; Administración de Empresas / Currículum",
    );
  });

  it("no falla con una unidad o dominio que ya no existe", () => {
    expect(describeAccess({ all_domains: false, unit_ids: ["x"], domain_ids: ["y"] }, units)).toContain("eliminad");
    expect(describeAccess({ all_domains: false, unit_ids: [], domain_ids: [] }, units)).toBe("Sin acceso");
  });
});

describe("describeModes y describeCost", () => {
  it("nombra los modos", () => {
    expect(describeModes(["literal", "razonamiento"])).toBe("Literal y Con razonamiento");
    expect(describeModes([])).toBe("Ninguno");
  });

  it("costo aproximado con precisión según la magnitud", () => {
    expect(describeCost(0.019)).toBe("unos 0.019 USD por consulta");
    expect(describeCost(0.0021)).toBe("unos 0.0021 USD por consulta");
    expect(describeCost(0.5)).toBe("unos 0.50 USD por consulta");
    expect(describeCost(null)).toMatch(/sin consultas/);
  });
});

describe("pruneCoveredDomains", () => {
  it("quita los dominios que ya cubre una unidad completa", () => {
    expect(pruneCoveredDomains(["u1"], ["d1", "d3"], units)).toEqual(["d3"]);
    expect(pruneCoveredDomains([], ["d1"], units)).toEqual(["d1"]);
  });
});
