import { useMutation, useQuery } from "@tanstack/react-query";
import { apiFetch } from "./client";
import { clearSession, getSession, saveSession } from "./session";

interface LoginResponse {
  token: string;
  expires_at: string;
  user: { username: string };
}

export function useLogin() {
  return useMutation({
    mutationFn: (input: { username: string; password: string }) =>
      apiFetch<LoginResponse>("/auth/login", { method: "POST", body: input }),
    onSuccess: (data) => saveSession({ token: data.token, username: data.user.username }),
  });
}

/** Cierra la sesión en el servidor y siempre la olvida aquí, aunque la llamada falle (sin conexión, token ya vencido). */
export function useLogout() {
  return useMutation({
    mutationFn: async () => {
      try {
        await apiFetch<void>("/auth/logout", { method: "POST" });
      } finally {
        clearSession();
      }
    },
  });
}

export function useChangePassword() {
  return useMutation({
    mutationFn: (input: { current_password: string; new_password: string }) =>
      apiFetch<void>("/auth/password", { method: "POST", body: input }),
  });
}

/** Al cargar, comprueba que la sesión guardada siga valiendo; si no, el cliente ya la olvidó (`session_invalid`). */
export function useSessionCheck() {
  const token = getSession()?.token ?? "";
  return useQuery({
    queryKey: ["session-check", token],
    queryFn: () => apiFetch<{ username: string; expires_at: string }>("/auth/me"),
    enabled: Boolean(token),
    retry: false,
    staleTime: Infinity,
  });
}
