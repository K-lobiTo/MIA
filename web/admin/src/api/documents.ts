import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./client";
import type { BulkDeleteResponse } from "./types";

function useDocumentMutation<TVariables, TResult>(fn: (variables: TVariables) => Promise<TResult>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: fn,
    // Con un fallo parcial también cambia el inventario: se refresca siempre que la petición termina.
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["inventory"] });
      void queryClient.invalidateQueries({ queryKey: ["images"] });
    },
  });
}

/** Elimina un documento por completo (feature 012). 404: ya no existía. */
export const useDeleteDocument = () =>
  useDocumentMutation((v: { domainId: string; documentId: string }) =>
    apiFetch<void>(`/domains/${v.domainId}/documents/${v.documentId}`, { method: "DELETE" }),
  );

/** Elimina varios documentos con una sola petición; el resultado es por documento. */
export const useBulkDeleteDocuments = () =>
  useDocumentMutation((documentIds: string[]) =>
    apiFetch<BulkDeleteResponse>("/documents/bulk-delete", { method: "POST", body: { document_ids: documentIds } }),
  );
