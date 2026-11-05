import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./client";
import type { ConsultaUser, ConsultaUserCreated, ConsultaUsersResponse } from "./types";

export function useConsultaUsers() {
  return useQuery({
    queryKey: ["consulta-users"],
    queryFn: () => apiFetch<ConsultaUsersResponse>("/consulta-users"),
  });
}

export interface ConsultaUserInput {
  username: string;
  unit_id: string | null;
  // Vacío o ausente: el servidor genera una.
  password?: string | null;
}

function useUserMutation<TVariables, TResult>(fn: (variables: TVariables) => Promise<TResult>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["consulta-users"] }),
  });
}

export const useCreateConsultaUser = () =>
  useUserMutation((body: ConsultaUserInput) =>
    apiFetch<ConsultaUserCreated>("/consulta-users", { method: "POST", body }),
  );

export const useUpdateConsultaUser = () =>
  useUserMutation((v: { id: string; active: boolean }) =>
    apiFetch<ConsultaUser>(`/consulta-users/${v.id}`, { method: "PATCH", body: { active: v.active } }),
  );

export const useResetConsultaPassword = () =>
  useUserMutation((v: { id: string; password?: string | null }) =>
    apiFetch<{ password: string }>(`/consulta-users/${v.id}/reset-password`, {
      method: "POST",
      body: { password: v.password ?? null },
    }),
  );
