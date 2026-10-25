import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./client";
import type { Bot, BotsResponse } from "./types";

export function useBots(enabled = true) {
  return useQuery({
    queryKey: ["bots"],
    queryFn: () => apiFetch<BotsResponse>("/bots"),
    enabled,
  });
}

export interface BotInput {
  name: string;
  kapso_number_id: string;
  artifact_id: string;
}

function useBotMutation<TVariables, TResult>(fn: (variables: TVariables) => Promise<TResult>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["bots"] }),
  });
}

export const useCreateBot = () =>
  useBotMutation((body: BotInput) => apiFetch<Bot>("/bots", { method: "POST", body }));

export const useUpdateBot = () =>
  useBotMutation((v: { id: string; changes: Partial<BotInput> & { active?: boolean } }) =>
    apiFetch<Bot>(`/bots/${v.id}`, { method: "PATCH", body: v.changes }),
  );
