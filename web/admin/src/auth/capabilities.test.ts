import { describe, expect, it } from "vitest";
import type { Me } from "../api/types";
import { capabilities, scopeLabel } from "./capabilities";

const unidad: Me = { email: "a@itcr.ac.cr", is_global: false, source: "entra", units: [{ id: "1", name: "Computación" }] };
const global: Me = { email: "g@itcr.ac.cr", is_global: true, source: "entra", units: [] };

describe("capabilities", () => {
  it("el alcance global puede todo lo exclusivo", () => {
    expect(capabilities(global)).toEqual({
      canCreateUnit: true,
      canSeeBalance: true,
      canUseAllDomains: true,
      canEditEquivalences: true,
      showGlobalCaps: true,
    });
  });

  it("el alcance de unidad no crea unidades ni ve el saldo", () => {
    expect(capabilities(unidad)).toEqual({
      canCreateUnit: false,
      canSeeBalance: false,
      canUseAllDomains: false,
      canEditEquivalences: false,
      showGlobalCaps: false,
    });
  });

  it("sin perfil no puede nada", () => {
    expect(capabilities(null).canCreateUnit).toBe(false);
    expect(capabilities(undefined).canSeeBalance).toBe(false);
    expect(capabilities(null).canEditEquivalences).toBe(false);
  });
});

describe("scopeLabel", () => {
  it("nombra el alcance", () => {
    expect(scopeLabel(global)).toBe("Global");
    expect(scopeLabel(unidad)).toBe("Computación");
    expect(
      scopeLabel({ ...unidad, units: [{ id: "1", name: "Computación" }, { id: "2", name: "Administración de Empresas" }] }),
    ).toBe("Computación, Administración de Empresas");
    expect(scopeLabel({ ...unidad, units: [] })).toBe("Sin programas");
  });
});
