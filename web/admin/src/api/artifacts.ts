import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./client";
import type { Artifact, ArtifactAccess, ArtifactCreated, ArtifactsResponse, ModeId } from "./types";

export function useArtifacts(enabled: boolean) {
  return useQuery({
    queryKey: ["artifacts"],
    queryFn: () => apiFetch<ArtifactsResponse>("/artifacts"),
    enabled,
  });
}

export interface ArtifactInput {
  description: string;
  access: ArtifactAccess;
  modes: ModeId[];
}

function useArtifactMutation<TVariables, TResult>(fn: (variables: TVariables) => Promise<TResult>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["artifacts"] }),
  });
}

export const useCreateArtifact = () =>
  useArtifactMutation((body: ArtifactInput & { name: string }) =>
    apiFetch<ArtifactCreated>("/artifacts", { method: "POST", body }),
  );

export const useUpdateArtifact = () =>
  useArtifactMutation((v: { id: string; changes: Partial<ArtifactInput> & { active?: boolean } }) =>
    apiFetch<Artifact>(`/artifacts/${v.id}`, { method: "PATCH", body: v.changes }),
  );

export const useRegenerateKey = () =>
  useArtifactMutation((id: string) =>
    apiFetch<{ key: string; key_prefix: string }>(`/artifacts/${id}/key`, { method: "POST" }),
  );
