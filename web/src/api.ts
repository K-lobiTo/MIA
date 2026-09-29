// Cliente mínimo de la API de MIA. Las rutas pasan por el proxy de Vite (/api -> MIA_API_URL).

export interface Domain {
  id: string;
  name: string;
  description: string;
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
    headers: { "content-type": "application/json", ...init?.headers },
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
