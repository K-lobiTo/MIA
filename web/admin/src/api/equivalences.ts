import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./client";
import type { Equivalence, EquivalenceInput, EquivalencesResponse } from "./types";

export function useEquivalences(enabled = true) {
  return useQuery({
    queryKey: ["equivalences"],
    queryFn: () => apiFetch<EquivalencesResponse>("/equivalences"),
    enabled,
  });
}

function useEquivalenceMutation<TVariables, TResult>(fn: (variables: TVariables) => Promise<TResult>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["equivalences"] }),
  });
}

export const useCreateEquivalence = () =>
  useEquivalenceMutation((body: EquivalenceInput) =>
    apiFetch<Equivalence>("/equivalences", { method: "POST", body }),
  );

export const useUpdateEquivalence = () =>
  useEquivalenceMutation((v: { id: string; changes: Partial<EquivalenceInput> }) =>
    apiFetch<Equivalence>(`/equivalences/${v.id}`, { method: "PATCH", body: v.changes }),
  );

export const useDeleteEquivalence = () =>
  useEquivalenceMutation((id: string) => apiFetch<void>(`/equivalences/${id}`, { method: "DELETE" }));
