// Cliente mínimo de la API de MIA. Las rutas pasan por el proxy de Vite (/api -> MIA_API_URL).

export interface Domain {
  id: string;
  unit_name: string | null;
  name: string;
  description: string;
}

// Clave de un artefacto registrado en el panel de administración: la API le muestra solo los
// dominios y modos que ese artefacto tiene permitidos. Se recuerda en este navegador.
const KEY_STORAGE = "mia.clave-artefacto";

export function getKey(): string {
  try {
    return localStorage.getItem(KEY_STORAGE) ?? "";
  } catch {
    return "";
  }
}

export function setKey(key: string): void {
  try {
    if (key) localStorage.setItem(KEY_STORAGE, key);
    else localStorage.removeItem(KEY_STORAGE);
  } catch {
    // Sin almacenamiento (modo privado): la clave solo vale hasta recargar la página.
  }
}

export interface Source {
  domain: string;
  document: string;
  excerpt: string;
}

export interface QueryResponse {
  answer: string;
  sources: Source[];
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: {
      "content-type": "application/json",
      ...(getKey() ? { "X-Artifact-Key": getKey() } : {}),
      ...init?.headers,
    },
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      // Cuerpo no JSON (p. ej. error del proxy): se usa el texto del estado.
    }
    throw new ApiError(response.status, detail);
  }
  return response.json() as Promise<T>;
}

export function listDomains(): Promise<Domain[]> {
  return request<Domain[]>("/domains");
}

export function query(domainIds: string[], question: string): Promise<QueryResponse> {
  return request<QueryResponse>("/query", {
    method: "POST",
    body: JSON.stringify({ domains: domainIds, question }),
  });
}
