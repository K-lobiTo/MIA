import type { Outcome, UsageResponse } from "../../api/types";

export type Metric = "spend_usd" | "queries" | "tokens";
export type GroupBy = "artifact" | "mode" | "model";

export const METRIC_LABEL: Record<Metric, string> = { spend_usd: "Gasto", queries: "Consultas", tokens: "Tokens" };
export const GROUP_LABEL: Record<GroupBy, string> = { artifact: "Artefacto", mode: "Modo", model: "Modelo" };

export const OUTCOME_LABEL: Record<Outcome, { text: string; className: string }> = {
  answered: { text: "Respondida", className: "badge badge-ok" },
  no_info: { text: "Sin información", className: "badge" },
  error: { text: "Error", className: "badge badge-danger" },
  rejected_cap: { text: "Rechazada por tope", className: "badge badge-warn" },
  rejected_permission: { text: "Rechazada por permisos", className: "badge badge-warn" },
};

export const MAX_SERIES = 8;
export const OTHER = "Otros";

export interface ChartData {
  buckets: string[];
  // Series en el orden en que se apilan (de mayor a menor total); "Otros" siempre al final.
  names: string[];
  // values[i][j]: valor de la serie j en la cubeta i.
  values: number[][];
  totals: number[];
  max: number;
}

/** Arma los datos de la gráfica apilada. Desde la serie 9 todo se pliega en "Otros": un noveno color
 * generado no se distinguiría de los demás (regla del método de visualización). */
export function buildChartData(series: UsageResponse["series"], metric: Metric): ChartData {
  const totalByName = new Map<string, number>();
  for (const point of series) {
    for (const [name, cell] of Object.entries(point.groups)) {
      totalByName.set(name, (totalByName.get(name) ?? 0) + cell[metric]);
    }
  }
  const ranked = [...totalByName.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "es"));
  const kept = ranked.slice(0, MAX_SERIES).map(([name]) => name);
  const folded = ranked.length > MAX_SERIES;
  const names = folded ? [...kept, OTHER] : kept;

  const values = series.map((point) => {
    const row = names.map(() => 0);
    for (const [name, cell] of Object.entries(point.groups)) {
      const index = kept.indexOf(name);
      row[index === -1 ? names.length - 1 : index] += cell[metric];
    }
    return row;
  });
  const totals = values.map((row) => row.reduce((a, b) => a + b, 0));
  return { buckets: series.map((p) => p.bucket), names, values, totals, max: Math.max(0, ...totals) };
}

/** Marcas "redondas" del eje vertical (0, 1 000, 2 000...), con un paso de 1, 2 o 5 por potencia de diez. */
export function niceTicks(max: number, count = 4): number[] {
  if (max <= 0) return [0, 1];
  const rough = max / count;
  const magnitude = 10 ** Math.floor(Math.log10(rough));
  const step = [1, 2, 5, 10].map((m) => m * magnitude).find((s) => s >= rough)!;
  const ticks: number[] = [];
  for (let value = 0; value < max + step * 0.999; value += step) ticks.push(Number(value.toPrecision(12)));
  return ticks;
}

export function formatUsd(value: number): string {
  const digits = value >= 1 ? 2 : value >= 0.01 ? 3 : 4;
  return `${value.toFixed(digits)} USD`;
}

export function formatTokens(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)} M`;
  if (value >= 10_000) return `${Math.round(value / 1000)} k`;
  return value.toLocaleString("es-CR");
}

export function formatMetric(metric: Metric, value: number): string {
  if (metric === "spend_usd") return formatUsd(value);
  if (metric === "tokens") return formatTokens(value);
  return value.toLocaleString("es-CR");
}

/** Etiqueta de una marca del eje vertical: solo el número, porque la unidad va en el título de la gráfica. */
export function formatAxis(metric: Metric, value: number): string {
  if (metric === "tokens") return formatTokens(value);
  if (metric === "queries") return String(Math.round(value));
  return String(Number(value.toPrecision(3)));
}

export function formatLatency(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return "sin datos";
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)} s` : `${Math.round(ms)} ms`;
}

/** Etiqueta del eje horizontal: "14:00" por hora, "8/10" por día. */
export function bucketLabel(bucket: string, kind: "hour" | "day"): string {
  if (kind === "hour") return bucket.slice(11, 16);
  const [, month, day] = bucket.split("-");
  return `${Number(day)}/${Number(month)}`;
}

export type DeltaTone = "good" | "bad" | "neutral";

export interface Delta {
  text: string;
  tone: DeltaTone;
  arrow: "▲" | "▼" | "=";
}

/** Variación frente al período anterior, para la tarjeta de un indicador. `upIsGood` dice si subir es
 * bueno (útiles), malo (errores, tiempo, gasto) o neutro (volumen de consultas); el color sigue esa
 * lectura y siempre va acompañado de la flecha y del texto, nunca solo color. */
export function describeDelta(
  change: number | null | undefined,
  unit: "%" | "pts",
  upIsGood: boolean | null,
): Delta | null {
  if (change === null || change === undefined) return null;
  if (change === 0) return { text: `0 ${unit}`, tone: "neutral", arrow: "=" };
  const sign = change > 0 ? "+" : "-";
  // Punto decimal, como el resto de la interfaz (0.50 USD).
  const text = `${sign}${Math.abs(change).toFixed(1).replace(/\.0$/, "")} ${unit}`;
  let tone: DeltaTone = "neutral";
  if (upIsGood !== null) tone = (change > 0) === upIsGood ? "good" : "bad";
  return { text, tone, arrow: change > 0 ? "▲" : "▼" };
}
