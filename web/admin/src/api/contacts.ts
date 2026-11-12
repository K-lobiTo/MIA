import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiDownload, apiFetch } from "./client";
import type { ContactStatus, ContactsResponse } from "./types";

export interface ContactFilters {
  bot_id?: string;
  status: ContactStatus[];
  has_email?: boolean;
}

export const PAGE_SIZE = 50;

/** Los filtros como parámetros de la API (`status` se repite una vez por estado). */
export function toQuery(filters: ContactFilters, extra: Record<string, string> = {}): string {
  const params = new URLSearchParams();
  if (filters.bot_id) params.set("bot_id", filters.bot_id);
  for (const status of filters.status) params.append("status", status);
  if (filters.has_email !== undefined) params.set("has_email", String(filters.has_email));
  for (const [key, value] of Object.entries(extra)) params.set(key, value);
  return params.toString();
}

export function useContacts(filters: ContactFilters, page: number, enabled = true) {
  return useQuery({
    queryKey: ["contacts", filters, page],
    queryFn: () => apiFetch<ContactsResponse>(`/contacts?${toQuery(filters, { page: String(page), page_size: String(PAGE_SIZE) })}`),
    enabled,
    placeholderData: (previous) => previous,
  });
}

/** Descarga los contactos del filtro (todos, no una página) como CSV. Cada descarga queda en el registro de administración. */
export function downloadContactsCsv(filters: ContactFilters): Promise<void> {
  const day = new Date().toISOString().slice(0, 10);
  return apiDownload(`/contacts?${toQuery(filters, { format: "csv" })}`, `mia-contactos-${day}.csv`);
}

export function useDeleteContact() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiFetch<void>(`/contacts/${id}`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["contacts"] }),
  });
}

/** Borra todos los contactos del filtro. `expected` es el conteo que la persona vio y confirmó: si cambió, la API responde 409. */
export function useDeleteFilteredContacts() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (v: { filters: ContactFilters; expected: number }) =>
      apiFetch<{ deleted: number }>(`/contacts?${toQuery(v.filters, { expected: String(v.expected) })}`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["contacts"] }),
  });
}
