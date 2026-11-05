// Sesión de un usuario de la Consulta (feature 015): el token y el nombre. Vive en memoria y se recuerda en el navegador
// (localStorage) para que sobreviva a recargar. Puede fallar o estar vacío (ventana privada, datos bloqueados), así que todo
// va en try/catch y la sesión queda al menos en memoria.
import { useSyncExternalStore } from "react";

const STORAGE_KEY = "mia-consulta-session";

export interface Session {
  token: string;
  username: string;
}

export function loadSession(): Session | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const data = JSON.parse(raw) as Partial<Session> | null;
    if (data && typeof data.token === "string" && typeof data.username === "string") {
      return { token: data.token, username: data.username };
    }
    return null;
  } catch {
    return null;
  }
}

let current: Session | null = loadSession();
const listeners = new Set<() => void>();

export function getSession(): Session | null {
  return current;
}

export function saveSession(session: Session): void {
  current = session;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  } catch {
    // Sin almacenamiento: la sesión queda solo en memoria hasta recargar.
  }
  listeners.forEach((listener) => listener());
}

export function clearSession(): void {
  current = null;
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Nada que borrar.
  }
  listeners.forEach((listener) => listener());
}

export function useSession(): Session | null {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    () => current,
  );
}
