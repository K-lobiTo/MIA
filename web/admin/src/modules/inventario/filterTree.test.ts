import { describe, expect, it } from "vitest";
import type { DocumentItem, Inventory } from "../../api/types";
import { filterInventory, normalize } from "./filterTree";

const doc = (id: string, filename: string): DocumentItem => ({
  id,
  filename,
  source_type: "pdf",
  status: "done",
  uploaded_at: "2026-10-07T00:00:00Z",
  folder_id: null,
});

const inventory: Inventory = {
  ingestion_enabled: true,
  unassigned_domains: [],
  units: [
    {
      id: "u1",
      name: "Computación",
      description: "",
      document_count: 3,
      domains: [
        {
          id: "d1",
          name: "Currículum",
          description: "",
          document_count: 3,
          documents: [doc("1", "plan.pdf")],
          folders: [
            {
              id: "f1",
              name: "Programas de curso",
              parent_id: null,
              document_count: 2,
              folders: [],
              documents: [doc("2", "Sistemas Operativos.pdf"), doc("3", "Redes.pdf")],
            },
          ],
        },
        { id: "d2", name: "Docentes", description: "", document_count: 0, folders: [], documents: [] },
      ],
    },
    { id: "u2", name: "Administración de Empresas", description: "", document_count: 0, domains: [] },
  ],
};

describe("normalize", () => {
  it("quita tildes y mayúsculas", () => {
    expect(normalize("  Currículum ")).toBe("curriculum");
  });
});

describe("filterInventory", () => {
  it("sin texto devuelve el inventario completo", () => {
    expect(filterInventory(inventory, "  ")).toBe(inventory);
  });

  it("encuentra un documento y conserva solo su rama", () => {
    const result = filterInventory(inventory, "sistemas");
    expect(result.units).toHaveLength(1);
    const domain = result.units[0].domains[0];
    expect(result.units[0].domains).toHaveLength(1);
    expect(domain.documents).toHaveLength(0);
    expect(domain.folders[0].documents.map((d) => d.filename)).toEqual(["Sistemas Operativos.pdf"]);
  });

  it("un dominio que coincide por nombre se muestra completo, sin importar tildes", () => {
    const result = filterInventory(inventory, "curriculum");
    expect(result.units[0].domains.map((d) => d.name)).toEqual(["Currículum"]);
    expect(result.units[0].domains[0].folders[0].documents).toHaveLength(2);
  });

  it("una unidad que coincide se muestra completa", () => {
    const result = filterInventory(inventory, "administracion");
    expect(result.units.map((u) => u.name)).toEqual(["Administración de Empresas"]);
  });

  it("una carpeta que coincide conserva todos sus documentos", () => {
    const result = filterInventory(inventory, "programas");
    expect(result.units[0].domains[0].folders[0].documents).toHaveLength(2);
    expect(result.units[0].domains[0].documents).toHaveLength(0);
  });

  it("sin coincidencias no deja nada", () => {
    const result = filterInventory(inventory, "zzz");
    expect(result.units).toEqual([]);
  });
});
