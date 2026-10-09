import { useMutation, useQuery } from "@tanstack/react-query";
import { QUERY_TIMEOUT_MS, apiFetch, useKey } from "./client";
import type { Config, Domain, ModeId, QueryResponse, Rating } from "./types";

export function useConfig() {
  const key = useKey();
  return useQuery({
    queryKey: ["config", key],
    queryFn: () => apiFetch<Config>("/config"),
    enabled: Boolean(key),
    // Al volver a la pestaña se refrescan los topes y los modos disponibles.
    refetchOnWindowFocus: true,
  });
}

export function useDomains() {
  const key = useKey();
  return useQuery({
    queryKey: ["domains", key],
    queryFn: () => apiFetch<Domain[]>("/domains"),
    enabled: Boolean(key),
  });
}

export interface AskInput {
  domains: string[];
  question: string;
  mode: ModeId;
}

export function useAsk() {
  return useMutation({
    mutationFn: (input: AskInput) =>
      apiFetch<QueryResponse>("/query", { method: "POST", body: input, timeoutMs: QUERY_TIMEOUT_MS }),
  });
}

export interface FeedbackInput {
  queryId: string;
  rating: Rating;
  comment?: string;
}

export function useFeedback() {
  return useMutation({
    mutationFn: ({ queryId, rating, comment }: FeedbackInput) =>
      apiFetch<void>(`/query/${queryId}/feedback`, {
        method: "POST",
        body: { rating, comment: comment?.trim() || undefined },
      }),
  });
}
