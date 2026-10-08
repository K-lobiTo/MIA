import { useSyncExternalStore } from "react";

// En desarrollo, el proxy de Vite atiende /api. Publicado como sitio estático se construye con
// VITE_API_URL apuntando a la API (que debe permitir el origen del sitio en CORS_ORIGINS).
const BASE = import.meta.env.VITE_API_URL ?? "/api";
const STORAGE_KEY = "mia-admin-key";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

// Almacenamiento: puede fallar o estar vacío (ventana privada, datos bloqueados), así que todo va en try/catch.
function read(): string {
  try {
    return localStorage.getItem(STORAGE_KEY) ?? "";
  } catch {
    return "";
  }
}

let currentKey = read();
const listeners = new Set<() => void>();

export function getAdminKey(): string {
  return currentKey;
}

export function setAdminKey(key: string): void {
  currentKey = key;
  try {
    if (key) localStorage.setItem(STORAGE_KEY, key);
    else localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Sin almacenamiento: la clave queda solo en memoria hasta cerrar la pestaña.
  }
  listeners.forEach((listener) => listener());
}

export function useAdminKey(): string {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    () => currentKey,
  );
}

// Se avisa a la interfaz cuando la API rechaza la clave, para volver a pedirla.
let onInvalidKey: () => void = () => {};
export function setInvalidKeyHandler(handler: () => void): void {
  onInvalidKey = handler;
}

export interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  formData?: FormData;
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, formData, headers, ...rest } = options;
  const finalHeaders: Record<string, string> = { ...(headers as Record<string, string>) };
  if (currentKey) finalHeaders["X-Admin-Key"] = currentKey;
  if (body !== undefined) finalHeaders["content-type"] = "application/json";

  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      ...rest,
      headers: finalHeaders,
      body: formData ?? (body !== undefined ? JSON.stringify(body) : undefined),
    });
  } catch {
    throw new ApiError(0, "No se pudo conectar con la API. Revisa la conexión e intenta de nuevo.");
  }

  if (response.status === 204) return undefined as T;
  const text = await response.text();
  let data: unknown = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  if (!response.ok) {
    const detail =
      typeof data === "object" && data !== null && "detail" in data
        ? String((data as { detail: unknown }).detail)
        : `Error ${response.status}`;
    // Una clave guardada que dejó de valer (se cambió en la API) se olvida y se vuelve a pedir.
    if (response.status === 401 && currentKey) {
      setAdminKey("");
      onInvalidKey();
    }
    throw new ApiError(response.status, detail);
  }
  return data as T;
}

export function apiUrl(path: string): string {
  return `${BASE}${path}`;
}
