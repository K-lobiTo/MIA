import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useRef, useState } from "react";
import { ApiError } from "../../api/client";
import { uploadDocument } from "../../api/inventoryMutations";
import { validateFile } from "./inventoryUtils";

export type UploadState = "queued" | "uploading" | "done" | "existing" | "error" | "rejected";

export interface UploadItem {
  id: number;
  file: File;
  domainId: string;
  folderId: string | null;
  destination: string;
  state: UploadState;
  message?: string;
}

export interface UploadTarget {
  domainId: string;
  folderId: string | null;
  destination: string;
}

/** Cola de subidas: valida cada archivo antes de subirlo (tipo y tamaño), sube de a uno para no
 * saturar la ingesta del servidor, y deja el resultado de cada uno a la vista. */
export function useUploads(maxMb: number) {
  const queryClient = useQueryClient();
  const [items, setItems] = useState<UploadItem[]>([]);
  const running = useRef(false);
  const queue = useRef<UploadItem[]>([]);
  const nextId = useRef(1);

  const patch = useCallback((id: number, changes: Partial<UploadItem>) => {
    setItems((current) => current.map((item) => (item.id === id ? { ...item, ...changes } : item)));
  }, []);

  const run = useCallback(async () => {
    if (running.current) return;
    running.current = true;
    while (queue.current.length > 0) {
      const item = queue.current.shift()!;
      patch(item.id, { state: "uploading", message: undefined });
      try {
        const document = await uploadDocument(item.domainId, item.folderId, item.file);
        patch(
          item.id,
          document.already_existed
            ? { state: "existing", message: "Ya existía en este dominio: no se volvió a procesar." }
            : { state: "done", message: "Subido: en cola para procesarse." },
        );
      } catch (caught) {
        patch(item.id, {
          state: "error",
          message: caught instanceof ApiError ? caught.message : "Falló la subida.",
        });
      }
      await queryClient.invalidateQueries({ queryKey: ["inventory"] });
    }
    running.current = false;
  }, [patch, queryClient]);

  const add = useCallback(
    (files: File[], target: UploadTarget) => {
      const created: UploadItem[] = files.map((file) => {
        const problem = validateFile(file, maxMb);
        return {
          id: nextId.current++,
          file,
          ...target,
          state: problem ? "rejected" : "queued",
          message: problem ?? undefined,
        };
      });
      setItems((current) => [...current, ...created]);
      queue.current.push(...created.filter((item) => item.state === "queued"));
      void run();
    },
    [maxMb, run],
  );

  const retry = useCallback(
    (id: number) => {
      const item = items.find((candidate) => candidate.id === id);
      if (!item) return;
      patch(id, { state: "queued", message: undefined });
      queue.current.push({ ...item, state: "queued" });
      void run();
    },
    [items, patch, run],
  );

  const dismiss = useCallback((id: number) => setItems((current) => current.filter((item) => item.id !== id)), []);
  const clearFinished = useCallback(
    () => setItems((current) => current.filter((item) => item.state === "queued" || item.state === "uploading")),
    [],
  );

  return { items, add, retry, dismiss, clearFinished };
}
