// @vitest-environment node
import { describe, expect, it } from "vitest";
import { approxQueries } from "./capMath";
import { MODE_LABEL, avgCostOf, describeModes } from "./accessUtils";

describe("los tres modos del artefacto (feature 020)", () => {
  it("el formulario los conoce con su nombre, en el orden literal, razonamiento y plantilla", () => {
    expect(Object.keys(MODE_LABEL)).toEqual(["literal", "razonamiento", "plantilla"]);
    expect(MODE_LABEL.plantilla).toBe("Plantilla");
    expect(describeModes(["literal", "razonamiento", "plantilla"])).toBe("Literal, Con razonamiento y Plantilla");
  });

  it("la plantilla se estima con el costo del razonamiento mientras no tenga consultas propias, y con él las consultas aproximadas", () => {
    const modos = [
      { id: "literal" as const, avg_cost_usd_7d: 0.001 },
      { id: "razonamiento" as const, avg_cost_usd_7d: 0.05 },
      { id: "plantilla" as const, avg_cost_usd_7d: null },
    ];
    expect(approxQueries(0.5, avgCostOf("plantilla", modos))).toBe(10);
    expect(approxQueries(0.5, avgCostOf("literal", modos))).toBe(500);
  });
});
