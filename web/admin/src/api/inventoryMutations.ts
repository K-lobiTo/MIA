import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./client";
import type { DomainCreated, Unit } from "./types";

export interface UploadedDocument {
  id: string;
  filename: string;
  status: string;
  folder_id: string | null;
  already_existed: boolean;
}

function useInventoryMutation<TVariables, TResult>(fn: (variables: TVariables) => Promise<TResult>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["inventory"] }),
  });
}

export const useCreateUnit = () =>
  useInventoryMutation((body: { name: string; description: string }) =>
    apiFetch<Unit>("/units", { method: "POST", body }),
  );

export const useCreateDomain = () =>
  useInventoryMutation((body: { unit_id: string; name: string; description: string }) =>
    apiFetch<DomainCreated>("/domains", { method: "POST", body }),
  );

export const useCreateFolder = () =>
  useInventoryMutation((v: { domainId: string; name: string; parentId: string | null }) =>
    apiFetch<{ id: string }>(`/domains/${v.domainId}/folders`, {
      method: "POST",
      body: { name: v.name, parent_id: v.parentId },
    }),
  );

export const useRenameFolder = () =>
  useInventoryMutation((v: { folderId: string; name: string }) =>
    apiFetch<{ id: string }>(`/folders/${v.folderId}`, { method: "PATCH", body: { name: v.name } }),
  );

export const useDeleteFolder = () =>
  useInventoryMutation((folderId: string) => apiFetch<void>(`/folders/${folderId}`, { method: "DELETE" }));

/** Sube un archivo a un dominio, opcionalmente a una de sus carpetas (INV-4). */
export function uploadDocument(domainId: string, folderId: string | null, file: File): Promise<UploadedDocument> {
  const formData = new FormData();
  formData.append("file", file);
  if (folderId) formData.append("folder_id", folderId);
  return apiFetch<UploadedDocument>(`/domains/${domainId}/documents`, { method: "POST", formData });
}
