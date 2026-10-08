import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { apiDownload, apiFetch } from "./client";
import type { BalanceResponse, ModeId, Outcome, QueryLogDetail, QueryLogPage, UsageResponse } from "./types";

export type PeriodName = "today" | "7d" | "30d" | "custom";

/** Filtros del módulo Uso: controlan todo lo que se ve (USO-1). */
export interface UsageFilters {
  period: PeriodName;
  from: string;
  to: string;
  artifactId: string;
  mode: "" | ModeId;
}

export const DEFAULT_FILTERS: UsageFilters = { period: "7d", from: "", to: "", artifactId: "", mode: "" };

/** Un período personalizado solo se consulta con las dos fechas puestas. */
export function filtersReady(filters: UsageFilters): boolean {
  return filters.period !== "custom" || (filters.from !== "" && filters.to !== "" && filters.from <= filters.to);
}

export function toParams(filters: UsageFilters, extra: Record<string, string | string[] | undefined> = {}): string {
  const params = new URLSearchParams({ period: filters.period });
  if (filters.period === "custom") {
    params.set("from", filters.from);
    params.set("to", filters.to);
  }
  if (filters.artifactId) params.append("artifact_id", filters.artifactId);
  if (filters.mode) params.set("mode", filters.mode);
  for (const [key, value] of Object.entries(extra)) {
    if (value === undefined) continue;
    for (const item of Array.isArray(value) ? value : [value]) params.append(key, item);
  }
  return params.toString();
}

export function useUsage(filters: UsageFilters, groupBy: string, enabled = true) {
  return useQuery({
    queryKey: ["usage", filters, groupBy],
    queryFn: () => apiFetch<UsageResponse>(`/usage?${toParams(filters, { group_by: groupBy })}`),
    enabled: enabled && filtersReady(filters),
    // Al cambiar un filtro se sigue mostrando lo anterior mientras llega lo nuevo, sin parpadeos.
    placeholderData: keepPreviousData,
  });
}

export function useQueryLog(filters: UsageFilters, page: number, outcome: "" | Outcome) {
  return useQuery({
    queryKey: ["usage-queries", filters, page, outcome],
    queryFn: () =>
      apiFetch<QueryLogPage>(`/usage/queries?${toParams(filters, { page: String(page), outcome: outcome || undefined })}`),
    enabled: filtersReady(filters),
    placeholderData: keepPreviousData,
  });
}

export function useQueryDetail(id: string | null) {
  return useQuery({
    queryKey: ["usage-query", id],
    queryFn: () => apiFetch<QueryLogDetail>(`/usage/queries/${id}`),
    enabled: id !== null,
  });
}

export function useBalance() {
  return useQuery({ queryKey: ["usage-balance"], queryFn: () => apiFetch<BalanceResponse>("/usage/balance") });
}

/** Descarga el registro del período en CSV; las preguntas solo se incluyen si se piden (USO-8). */
export function downloadCsv(filters: UsageFilters, includeQuestions: boolean): Promise<void> {
  const query = toParams(filters, { format: "csv", include_questions: includeQuestions ? "true" : undefined });
  return apiDownload(`/usage/queries?${query}`, "mia-consultas.csv");
}
