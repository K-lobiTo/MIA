import { describe, expect, it } from "vitest";
import type { Equivalence } from "../../api/types";
import {
  isDuplicate,
  normalizeForm,
  normalizeSigla,
  validateEquivalence,
} from "./equivalenciasUtils";

const tfg: Equivalence = {
  id: "1",
  sigla: "TFG",
  form: "Trabajo Final de Graduación",
  created_by: "automatizacion",
  created_at: "2026-10-19T00:00:00",
  updated_by: null,
  updated_at: null,
};

describe("normalizeSigla y normalizeForm", () => {
  it("quitan tildes, mayúsculas, puntos y espacios de la sigla", () => {
    expect(normalizeSigla("T.F.G.")).toBe("tfg");
    expect(normalizeSigla(" Mg ti ")).toBe("mgti");
  });

  it("dejan la forma en palabras minúsculas sin tildes con un solo espacio", () => {
    expect(normalizeForm("  Trabajo   FINAL de Graduación ")).toBe("trabajo final de graduacion");
    expect(normalizeForm("")).toBe("");
  });
});

describe("isDuplicate", () => {
  it("compara sin mayúsculas, tildes ni espacios", () => {
    expect(isDuplicate({ sigla: "t.f.g", form: "TRABAJO final  de graduacion" }, [tfg])).toBe(tfg);
    expect(isDuplicate({ sigla: "TFG", form: "Tesis de grado" }, [tfg])).toBeNull();
  });

  it("ignora la equivalencia que se está editando", () => {
    expect(isDuplicate({ sigla: "TFG", form: "Trabajo Final de Graduación" }, [tfg], "1")).toBeNull();
  });
});

describe("validateEquivalence", () => {
  const valid = { sigla: "PLN", form: "Procesamiento de Lenguaje Natural" };

  it("acepta un par bueno", () => {
    expect(validateEquivalence(valid, [tfg])).toBeNull();
  });

  it("rechaza la sigla vacía, corta, larga o con caracteres raros", () => {
    expect(validateEquivalence({ ...valid, sigla: "  " }, [])).toMatch(/sigla no puede estar vacía/);
    expect(validateEquivalence({ ...valid, sigla: "PL" }, [])).toMatch(/de 3 a 20/);
    expect(validateEquivalence({ ...valid, sigla: "P".repeat(21) }, [])).toMatch(/de 3 a 20/);
    expect(validateEquivalence({ ...valid, sigla: "PLN!" }, [])).toMatch(/letras y dígitos/);
  });

  it("rechaza la forma vacía, corta, larga, sin palabras de 3 letras o igual a la sigla", () => {
    expect(validateEquivalence({ ...valid, form: "" }, [])).toMatch(/forma desarrollada no puede estar vacía/);
    expect(validateEquivalence({ ...valid, form: "ab" }, [])).toMatch(/de 3 a 120/);
    expect(validateEquivalence({ ...valid, form: "x".repeat(121) }, [])).toMatch(/de 3 a 120/);
    expect(validateEquivalence({ ...valid, form: "de la en" }, [])).toMatch(/palabra de 3 letras/);
    expect(validateEquivalence({ ...valid, form: "P.L.N." }, [])).toMatch(/igual a la sigla/);
  });

  it("rechaza un par que ya existe y nombra el existente", () => {
    expect(validateEquivalence({ sigla: "tfg", form: "trabajo final de graduación" }, [tfg])).toBe(
      "Ya existe la equivalencia «TFG» = «Trabajo Final de Graduación».",
    );
  });
});
