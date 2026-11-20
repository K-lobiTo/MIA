import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./client";

/** Respuesta de agregar una página web (feature 022): el documento creado, o el que ya existía con el mismo texto. */
export interface WebPageResult {
  id: string;
  filename: string;
  source_type: string;
  status: string;
  folder_id: string | null;
  status_note: string | null;
  already_existed: boolean;
  source_url: string | null;
  uploaded_at: string | null;
}

export interface AddWebPageInput {
  domainId: string;
  url: string;
  name: string;
  folderId: string | null;
}

/** Lee una página y la agrega como documento del dominio. Un rechazo (inicio de sesión, anti-bot, etc.) llega como ApiError con
 * el mensaje y el código de la API. */
export function addWebPage({ domainId, url, name, folderId }: AddWebPageInput): Promise<WebPageResult> {
  return apiFetch<WebPageResult>(`/domains/${domainId}/web-pages`, {
    method: "POST",
    body: { url, name: name.trim() === "" ? null : name, folder_id: folderId },
  });
}

export const useAddWebPage = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: addWebPage,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["inventory"] }),
  });
};

export interface DocumentText {
  text: string;
  source_url: string | null;
  read_at: string | null;
  filename: string;
}

/** El texto extraído de un documento web, para revisarlo. */
export function fetchDocumentText(domainId: string, documentId: string): Promise<DocumentText> {
  return apiFetch<DocumentText>(`/domains/${domainId}/documents/${documentId}/text`);
}

export const useDocumentText = (domainId: string, documentId: string) =>
  useQuery({
    queryKey: ["document-text", domainId, documentId],
    queryFn: () => fetchDocumentText(domainId, documentId),
    // El texto de un documento web no cambia (para renovarlo se elimina y se vuelve a agregar).
    staleTime: Infinity,
  });
