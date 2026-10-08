/** Funciones puras de los topes de gasto (ART-8 a ART-10). */

/** Lee un monto en USD escrito por una persona ("0.5", "0,50"). null si no es un número mayor que 0. */
export function parseUsd(text: string): number | null {
  const value = Number.parseFloat(text.trim().replace(",", "."));
  return Number.isFinite(value) && value > 0 ? value : null;
}

export function formatUsd(value: number): string {
  return `${value.toFixed(value >= 10 ? 1 : 2)} USD`;
}

/** Porcentaje del tope ya gastado, entre 0 y 100, para la barra de avance. */
export function percentUsed(spent: number, cap: number): number {
  if (cap <= 0) return 100;
  return Math.max(0, Math.min(100, (spent / cap) * 100));
}

/** Cuántas consultas alcanza un tope según el costo medio reciente del modo; null si no se puede estimar. */
export function approxQueries(cap: number, avgCost: number | null | undefined): number | null {
  if (!avgCost || avgCost <= 0) return null;
  return Math.floor(cap / avgCost);
}

/** Estado de la barra: normal, cerca del tope (desde 80 %) o alcanzado. */
export function meterLevel(spent: number, cap: number): "ok" | "warn" | "full" {
  const percent = percentUsed(spent, cap);
  if (spent >= cap) return "full";
  return percent >= 80 ? "warn" : "ok";
}

/** Valida los dos topes del formulario y devuelve el motivo si no son válidos (ART-8). */
export function validateCaps(dailyText: string, reasoningText: string): string | null {
  const daily = parseUsd(dailyText);
  if (daily === null) return "El tope diario debe ser un monto mayor que 0.";
  if (reasoningText.trim() === "") return null;
  const reasoning = parseUsd(reasoningText);
  if (reasoning === null) return "El tope del modo con razonamiento debe ser un monto mayor que 0, o quedar vacío.";
  if (reasoning > daily) return "El tope del modo con razonamiento no puede superar el tope diario total.";
  return null;
}
