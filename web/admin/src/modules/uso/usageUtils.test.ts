import { describe, expect, it } from "vitest";
import type { UsageResponse } from "../../api/types";
import { MAX_SERIES, OTHER, bucketLabel, formatAxis, buildChartData, describeDelta, formatLatency, formatTokens, formatUsd, niceTicks } from "./usageUtils";

const cell = (spend: number, queries = 1, tokens = 100) => ({ spend_usd: spend, queries, tokens });

describe("buildChartData", () => {
  const series: UsageResponse["series"] = [
    { bucket: "2026-10-07", groups: { A: cell(1), B: cell(3) } },
    { bucket: "2026-10-08", groups: { A: cell(2) } },
    { bucket: "2026-10-09", groups: {} },
  ];

  it("apila de mayor a menor total y rellena con 0 las cubetas vacías", () => {
    const data = buildChartData(series, "spend_usd");
    expect(data.names).toEqual(["A", "B"]); // A suma 3 y B suma 3: empata y desempata por nombre
    expect(data.values).toEqual([[1, 3], [2, 0], [0, 0]]);
    expect(data.totals).toEqual([4, 2, 0]);
    expect(data.max).toBe(4);
  });

  it("cambia de métrica", () => {
    const data = buildChartData(series, "queries");
    expect(data.totals).toEqual([2, 1, 0]);
  });

  it("desde la serie 9 pliega todo en 'Otros' sin inventar colores", () => {
    const groups = Object.fromEntries(Array.from({ length: 11 }, (_, i) => [`M${String(i).padStart(2, "0")}`, cell(11 - i)]));
    const data = buildChartData([{ bucket: "b", groups }], "spend_usd");
    expect(data.names).toHaveLength(MAX_SERIES + 1);
    expect(data.names.at(-1)).toBe(OTHER);
    // M08, M09 y M10 (3 + 2 + 1) quedan en Otros
    expect(data.values[0].at(-1)).toBe(6);
    expect(data.totals[0]).toBe(66);
  });

  it("sin datos no falla", () => {
    expect(buildChartData([], "tokens")).toEqual({ buckets: [], names: [], values: [], totals: [], max: 0 });
  });
});

describe("niceTicks", () => {
  it("elige pasos redondos que cubren el máximo", () => {
    expect(niceTicks(0)).toEqual([0, 1]);
    expect(niceTicks(0.8)).toEqual([0, 0.2, 0.4, 0.6, 0.8]);
    expect(niceTicks(4300)).toEqual([0, 2000, 4000, 6000]);
    const ticks = niceTicks(37);
    expect(ticks[0]).toBe(0);
    expect(ticks.at(-1)!).toBeGreaterThanOrEqual(37);
  });
});

describe("formatos", () => {
  it("dinero con más decimales cuanto menor es el monto", () => {
    expect(formatUsd(3.4237)).toBe("3.42 USD");
    expect(formatUsd(0.023)).toBe("0.023 USD");
    expect(formatUsd(0.0021)).toBe("0.0021 USD");
  });

  it("tokens compactos", () => {
    expect(formatTokens(1_900_000)).toBe("1.9 M");
    expect(formatTokens(12_400)).toBe("12 k");
    expect(formatLatency(6100)).toBe("6.1 s");
    expect(formatLatency(480)).toBe("480 ms");
    expect(formatLatency(null)).toBe("sin datos");
  });

  it("las marcas del eje no llevan unidad ni se alargan", () => {
    expect(formatAxis("spend_usd", 0.15)).toBe("0.15");
    expect(formatAxis("spend_usd", 0)).toBe("0");
    expect(formatAxis("spend_usd", 2)).toBe("2");
    expect(formatAxis("queries", 25)).toBe("25");
    expect(formatAxis("tokens", 50000)).toBe("50 k");
  });

  it("etiquetas del eje", () => {
    expect(bucketLabel("2026-10-08T14:00", "hour")).toBe("14:00");
    expect(bucketLabel("2026-10-08", "day")).toBe("8/10");
  });
});

describe("describeDelta", () => {
  it("el color depende de si subir es bueno", () => {
    expect(describeDelta(12.1, "%", false)).toEqual({ text: "+12.1 %", tone: "bad", arrow: "▲" });
    expect(describeDelta(-3.2, "%", false)).toEqual({ text: "-3.2 %", tone: "good", arrow: "▼" });
    expect(describeDelta(4, "pts", true)).toEqual({ text: "+4 pts", tone: "good", arrow: "▲" });
    expect(describeDelta(5.1, "%", null)?.tone).toBe("neutral");
  });

  it("sin período anterior no hay variación; sin cambio queda neutra", () => {
    expect(describeDelta(null, "%", false)).toBeNull();
    expect(describeDelta(undefined, "pts", true)).toBeNull();
    expect(describeDelta(0, "%", false)).toEqual({ text: "0 %", tone: "neutral", arrow: "=" });
  });
});
