import { describeAccessError, EXPIRED } from "../auth/errors";
import { currentEmail, getAdminKey, getIdToken, reject, usingKey } from "../auth/session";

// En desarrollo, el proxy de Vite atiende /api. Publicado como sitio estático se construye con
// VITE_API_URL apuntando a la API (que debe permitir el origen del sitio en CORS_ORIGINS).
const BASE = import.meta.env.VITE_API_URL ?? "/api";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public code?: string,
  ) {
    super(message);
  }
}

const NO_CONNECTION = "No se pudo conectar con la API. Revisa la conexión e intenta de nuevo.";

export interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  formData?: FormData;
}

async function fetchWith(path: string, init: RequestInit, token: string): Promise<Response> {
  const headers = { ...(init.headers as Record<string, string>), Authorization: `Bearer ${token}` };
  try {
    return await fetch(`${BASE}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, NO_CONNECTION);
  }
}

/** Envía la petición con el token de identidad. Ante un 401 (vencido) renueva el token y reintenta una
 * sola vez; si la renovación no es posible, la sesión pasa a "vencida". */
async function send(path: string, init: RequestInit): Promise<Response> {
  if (usingKey()) {
    // Entrada con la clave de administración: va en X-Admin-Key y no hay token que renovar.
    const headers = { ...(init.headers as Record<string, string>), "X-Admin-Key": getAdminKey() };
    try {
      return await fetch(`${BASE}${path}`, { ...init, headers });
    } catch {
      throw new ApiError(0, NO_CONNECTION);
    }
  }
  const expired = () => {
    reject(EXPIRED);
    return new ApiError(401, EXPIRED.message, "token_expired");
  };
  let token: string;
  try {
    token = await getIdToken();
  } catch {
    throw expired();
  }
  let response = await fetchWith(path, init, token);
  if (response.status === 401) {
    try {
      token = await getIdToken(true);
    } catch {
      throw expired();
    }
    response = await fetchWith(path, init, token);
  }
  return response;
}

async function failure(response: Response): Promise<ApiError> {
  const text = await response.text();
  let data: unknown = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  const body = typeof data === "object" && data !== null ? (data as { detail?: unknown; code?: unknown }) : {};
  const detail = body.detail !== undefined ? String(body.detail) : `Error ${response.status}`;
  const code = typeof body.code === "string" ? body.code : undefined;
  // Un rechazo de acceso (cuenta no autorizada, sin segundo factor, sesión vencida...) deja la sesión
  // inutilizable: se muestra su pantalla. Los demás errores son de la operación.
  const problem = describeAccessError(response.status, code, currentEmail(), usingKey());
  if (problem) reject(problem);
  return new ApiError(response.status, detail, code);
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, formData, headers, ...rest } = options;
  const finalHeaders: Record<string, string> = { ...(headers as Record<string, string>) };
  if (body !== undefined) finalHeaders["content-type"] = "application/json";

  const response = await send(path, {
    ...rest,
    headers: finalHeaders,
    body: formData ?? (body !== undefined ? JSON.stringify(body) : undefined),
  });
  if (response.status === 204) return undefined as T;
  if (!response.ok) throw await failure(response);
  const text = await response.text();
  try {
    return (text ? JSON.parse(text) : null) as T;
  } catch {
    return text as T;
  }
}

/** Descarga un archivo de la API (p. ej. el CSV del registro) con la sesión iniciada. */
export async function apiDownload(path: string, filename: string): Promise<void> {
  const response = await send(path, {});
  if (!response.ok) throw await failure(response);
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export function apiUrl(path: string): string {
  return `${BASE}${path}`;
}
