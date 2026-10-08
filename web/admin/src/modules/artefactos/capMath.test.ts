import { describe, expect, it } from "vitest";
import { approxQueries, formatUsd, meterLevel, parseUsd, percentUsed, validateCaps } from "./capMath";

describe("parseUsd", () => {
  it("acepta punto o coma decimal", () => {
    expect(parseUsd("0.5")).toBe(0.5);
    expect(parseUsd(" 1,25 ")).toBe(1.25);
  });

  it("rechaza vacío, texto, cero y negativos", () => {
    for (const text of ["", "abc", "0", "-1", "  "]) expect(parseUsd(text)).toBeNull();
  });
});

describe("percentUsed y meterLevel", () => {
  it("limita el porcentaje entre 0 y 100", () => {
    expect(percentUsed(0.6, 1.2)).toBeCloseTo(50);
    expect(percentUsed(5, 1)).toBe(100);
    expect(percentUsed(-1, 1)).toBe(0);
    expect(percentUsed(1, 0)).toBe(100);
  });

  it("avisa desde 80 % y marca el tope alcanzado", () => {
    expect(meterLevel(0.5, 1)).toBe("ok");
    expect(meterLevel(0.8, 1)).toBe("warn");
    expect(meterLevel(1, 1)).toBe("full");
    expect(meterLevel(2, 1)).toBe("full");
  });
});

describe("approxQueries", () => {
  it("divide el tope por el costo medio", () => {
    expect(approxQueries(0.5, 0.019)).toBe(26);
    expect(approxQueries(2, 0.5)).toBe(4);
  });

  it("sin costo medio no estima", () => {
    expect(approxQueries(0.5, null)).toBeNull();
    expect(approxQueries(0.5, 0)).toBeNull();
    expect(approxQueries(0.5, undefined)).toBeNull();
  });
});

describe("validateCaps", () => {
  it("acepta un tope total solo, o con uno menor de razonamiento", () => {
    expect(validateCaps("0.50", "")).toBeNull();
    expect(validateCaps("2", "1.5")).toBeNull();
    expect(validateCaps("2", "2")).toBeNull();
  });

  it("rechaza topes inválidos con el motivo", () => {
    expect(validateCaps("", "")).toMatch(/mayor que 0/);
    expect(validateCaps("0", "")).toMatch(/mayor que 0/);
    expect(validateCaps("1", "2")).toMatch(/no puede superar/);
    expect(validateCaps("1", "abc")).toMatch(/razonamiento/);
  });
});

describe("formatUsd", () => {
  it("muestra dos decimales y uno desde 10", () => {
    expect(formatUsd(0.5)).toBe("0.50 USD");
    expect(formatUsd(12.34)).toBe("12.3 USD");
  });
});
