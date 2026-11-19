import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./client";
import type { ArtifactTemplate, ArtifactTemplatesResponse } from "./types";

const key = (artifactId: string) => ["artifact-templates", artifactId];

/** Las plantillas de un artefacto, con su contenido y los límites (feature 020). */
export function useArtifactTemplates(artifactId: string) {
  return useQuery({
    queryKey: key(artifactId),
    queryFn: () => apiFetch<ArtifactTemplatesResponse>(`/artifacts/${artifactId}/templates`),
  });
}

/** Tras escribir se refresca la lista y el listado de artefactos (que muestra la cantidad de plantillas). */
function useTemplateMutation<TVariables, TResult>(artifactId: string, fn: (variables: TVariables) => Promise<TResult>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: key(artifactId) });
      void queryClient.invalidateQueries({ queryKey: ["artifacts"] });
    },
  });
}

export interface TemplateInput {
  name: string;
  content: string;
}

export const useCreateArtifactTemplate = (artifactId: string) =>
  useTemplateMutation(artifactId, (body: TemplateInput) =>
    apiFetch<ArtifactTemplate>(`/artifacts/${artifactId}/templates`, { method: "POST", body }),
  );

export const useUpdateArtifactTemplate = (artifactId: string) =>
  useTemplateMutation(artifactId, (v: { id: string; changes: TemplateInput; expectedUpdatedAt?: string }) =>
    apiFetch<ArtifactTemplate>(`/artifacts/${artifactId}/templates/${v.id}`, {
      method: "PUT",
      body: { ...v.changes, expected_updated_at: v.expectedUpdatedAt },
    }),
  );

export const useDeleteArtifactTemplate = (artifactId: string) =>
  useTemplateMutation(artifactId, (id: string) =>
    apiFetch<void>(`/artifacts/${artifactId}/templates/${id}`, { method: "DELETE" }),
  );

/** Lee un `.docx` o `.txt` en la API y devuelve su texto, para revisarlo antes de guardarlo; no guarda nada. */
export const useExtractArtifactTemplate = (artifactId: string) =>
  useMutation({
    mutationFn: (file: File) => {
      const formData = new FormData();
      formData.append("file", file);
      return apiFetch<{ text: string }>(`/artifacts/${artifactId}/templates/extract`, { method: "POST", formData });
    },
  });
