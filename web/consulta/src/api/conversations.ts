import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./client";
import type { ConversationsResponse, StoredConversation } from "./types";

export const CONVERSATIONS_KEY = ["conversations"];

/** La lista de conversaciones guardadas de la persona con sesión. */
export function useConversations(enabled: boolean) {
  return useQuery({
    queryKey: CONVERSATIONS_KEY,
    queryFn: () => apiFetch<ConversationsResponse>("/conversations"),
    enabled,
  });
}

export function fetchConversation(id: string): Promise<StoredConversation> {
  return apiFetch<StoredConversation>(`/conversations/${encodeURIComponent(id)}`);
}

/** Refresca la lista (tras responder una pregunta, borrar o cerrar sesión). */
export function useRefreshConversations() {
  const client = useQueryClient();
  return () => client.invalidateQueries({ queryKey: CONVERSATIONS_KEY });
}

export function useDeleteConversation() {
  const refresh = useRefreshConversations();
  return useMutation({
    mutationFn: (id: string) => apiFetch<void>(`/conversations/${encodeURIComponent(id)}`, { method: "DELETE" }),
    onSettled: () => refresh(),
  });
}

export function useDeleteAllConversations() {
  const refresh = useRefreshConversations();
  return useMutation({
    mutationFn: () => apiFetch<void>("/conversations", { method: "DELETE" }),
    onSettled: () => refresh(),
  });
}

