import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./client";
import type { ImageItem, ImagesResponse } from "./types";

/** Las imágenes de un documento, por posición (feature 011). */
export function useDocumentImages(domainId: string, documentId: string, enabled = true) {
  return useQuery({
    queryKey: ["images", documentId],
    queryFn: () => apiFetch<ImagesResponse>(`/domains/${domainId}/documents/${documentId}/images`),
    enabled,
  });
}

const base = (domainId: string, documentId: string) => `/domains/${domainId}/documents/${documentId}/images`;

function useImageMutation<TVariables extends { documentId: string }, TResult>(fn: (variables: TVariables) => Promise<TResult>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: (_result, variables) => {
      void queryClient.invalidateQueries({ queryKey: ["images", variables.documentId] });
      // El contador de imágenes de cada documento sale del inventario.
      void queryClient.invalidateQueries({ queryKey: ["inventory"] });
    },
  });
}

interface Ref {
  domainId: string;
  documentId: string;
}

export const useAddImage = () =>
  useImageMutation((v: Ref & { file: File; caption: string }) => {
    const formData = new FormData();
    formData.append("file", v.file);
    if (v.caption.trim() !== "") formData.append("caption", v.caption.trim());
    return apiFetch<ImageItem>(base(v.domainId, v.documentId), { method: "POST", formData });
  });

export const useReplaceImage = () =>
  useImageMutation((v: Ref & { imageId: string; file: File }) => {
    const formData = new FormData();
    formData.append("file", v.file);
    return apiFetch<ImageItem>(`${base(v.domainId, v.documentId)}/${v.imageId}`, { method: "PUT", formData });
  });

export const useUpdateCaption = () =>
  useImageMutation((v: Ref & { imageId: string; caption: string }) =>
    apiFetch<ImageItem>(`${base(v.domainId, v.documentId)}/${v.imageId}`, { method: "PATCH", body: { caption: v.caption } }),
  );

export const useReorderImages = () =>
  useImageMutation((v: Ref & { imageIds: string[] }) =>
    apiFetch<{ images: ImageItem[] }>(`${base(v.domainId, v.documentId)}/order`, { method: "PUT", body: { image_ids: v.imageIds } }),
  );

export const useDeleteImage = () =>
  useImageMutation((v: Ref & { imageId: string }) =>
    apiFetch<void>(`${base(v.domainId, v.documentId)}/${v.imageId}`, { method: "DELETE" }),
  );
