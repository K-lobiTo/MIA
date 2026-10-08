import { describe, expect, it } from "vitest";
import { assignColors } from "./colors";

describe("assignColors", () => {
  it("asigna los pasos en el orden fijo de la paleta", () => {
    const colors = assignColors(["A", "B", "C"], new Map());
    expect(colors).toEqual({ A: "var(--series-1)", B: "var(--series-2)", C: "var(--series-3)" });
  });

  it("un filtro que quita series no repinta a las que quedan", () => {
    const memory = new Map<string, number>();
    const antes = assignColors(["A", "B", "C"], memory);
    const despues = assignColors(["C", "A"], memory);
    expect(despues.A).toBe(antes.A);
    expect(despues.C).toBe(antes.C);
  });

  it("una serie que aparece después toma un paso libre, sin repetir los visibles", () => {
    const memory = new Map<string, number>();
    assignColors(["A", "B"], memory);
    const colors = assignColors(["A", "B", "Nueva"], memory);
    expect(new Set(Object.values(colors)).size).toBe(3);
    expect(colors.Nueva).toBe("var(--series-3)");
  });

  it("'Otros' va en gris neutro y no gasta un paso de la paleta", () => {
    const colors = assignColors(["A", "Otros", "B"], new Map());
    expect(colors.Otros).toBe("var(--series-other)");
    expect(colors.B).toBe("var(--series-2)");
  });

  it("los ocho pasos visibles a la vez nunca se repiten", () => {
    const names = Array.from({ length: 8 }, (_, i) => `S${i}`);
    expect(new Set(Object.values(assignColors(names, new Map()))).size).toBe(8);
  });
});
