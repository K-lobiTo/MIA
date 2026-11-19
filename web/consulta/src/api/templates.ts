import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch, useKey } from "./client";
import { useSession } from "./session";
import type { Template, TemplatesResponse } from "./types";

/** Las plantillas visibles en este artefacto y, con sesión, las personales de la persona (feature 020). La clave de la
 * consulta incluye el artefacto y la sesión: al cambiar de cuenta o de artefacto no se mezclan las listas. */
export function useTemplates() {
  const key = useKey();
  const session = useSession();
  return useQuery({
    queryKey: ["templates", key, session?.token ?? null],
    queryFn: () => apiFetch<TemplatesResponse>("/templates"),
    enabled: Boolean(key),
  });
}

export interface TemplateInput {
  name: string;
  content: string;
  /** `artifact`: solo para este artefacto; `all`: para todos los artefactos donde inicie sesión. */
  scope: "artifact" | "all";
}

/** Tras escribir se refresca la lista de plantillas. */
function useTemplateMutation<TVariables, TResult>(fn: (variables: TVariables) => Promise<TResult>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => client.invalidateQueries({ queryKey: ["templates"] }),
  });
}

export const useCreateTemplate = () =>
  useTemplateMutation((body: TemplateInput) => apiFetch<Template>("/templates", { method: "POST", body }));

export const useUpdateTemplate = () =>
  useTemplateMutation((v: { id: string; changes: TemplateInput; expectedUpdatedAt?: string }) =>
    apiFetch<Template>(`/templates/${encodeURIComponent(v.id)}`, {
      method: "PUT",
      body: { ...v.changes, expected_updated_at: v.expectedUpdatedAt },
    }),
  );

export const useDeleteTemplate = () =>
  useTemplateMutation((id: string) => apiFetch<void>(`/templates/${encodeURIComponent(id)}`, { method: "DELETE" }));

/** Lee un `.docx` o `.txt` en la API y devuelve su texto, para revisarlo antes de guardarlo; no guarda nada. */
export const useExtractTemplate = () =>
  useMutation({
    mutationFn: (file: File) => {
      const formData = new FormData();
      formData.append("file", file);
      return apiFetch<{ text: string }>("/templates/extract", { method: "POST", formData });
    },
  });
