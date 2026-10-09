import { useSyncExternalStore } from "react";

// En desarrollo, el proxy de Vite atiende /api. Publicado como sitio estático se construye con
// VITE_API_URL apuntando a la API (que debe permitir el origen del sitio en CORS_ORIGINS).
const BASE = import.meta.env.VITE_API_URL ?? "/api";
const STORAGE_KEY = "mia-consulta-key";

/** Espera de una consulta: el razonamiento puede tardar decenas de segundos (spec FR-019). */
export const QUERY_TIMEOUT_MS = 200_000;
const DEFAULT_TIMEOUT_MS = 30_000;

/** `status` 0: sin conexión; -1: tiempo agotado; el resto, el estado HTTP. */
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

export function getKey(): string {
  return currentKey;
}

export function setKey(key: string): void {
  currentKey = key;
  try {
    if (key) localStorage.setItem(STORAGE_KEY, key);
    else localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Sin almacenamiento: la clave queda solo en memoria hasta cerrar la pestaña.
  }
  listeners.forEach((listener) => listener());
}

export function useKey(): string {
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

/** Texto legible del `detail` de la API: un texto, o el primer mensaje de una lista de errores 422. */
export function detailText(data: unknown, status: number): string {
  if (typeof data === "object" && data !== null && "detail" in data) {
    const detail = (data as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0] as { msg?: unknown };
      if (typeof first?.msg === "string") return first.msg;
    }
  }
  return `Error ${status}`;
}

export async function apiFetch<T>(
  path: string,
  options: { method?: string; body?: unknown; timeoutMs?: number } = {},
): Promise<T> {
  const { method = "GET", body, timeoutMs = DEFAULT_TIMEOUT_MS } = options;
  const headers: Record<string, string> = {};
  if (currentKey) headers["X-Artifact-Key"] = currentKey;
  if (body !== undefined) headers["content-type"] = "application/json";

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError(-1, "MIA tardó demasiado en responder.");
    }
    throw new ApiError(0, "No se pudo conectar con MIA. Revisa tu conexión.");
  } finally {
    clearTimeout(timer);
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
    // Una clave guardada que dejó de valer (se regeneró o se desactivó) se olvida y se vuelve a pedir.
    if (response.status === 401 && currentKey) {
      setKey("");
      onInvalidKey();
    }
    throw new ApiError(response.status, detailText(data, response.status));
  }
  return data as T;
}
