import type { Source } from "../api/types";

export interface CitedDocument {
  document: string;
  domain: string;
}

/** Documentos citados sin repetir, en el orden en que aparecen (un mismo nombre en otro dominio es otro documento). */
export function uniqueDocuments(sources: Source[]): CitedDocument[] {
  const seen = new Set<string>();
  const result: CitedDocument[] = [];
  for (const { document, domain } of sources) {
    const id = `${domain}\u0000${document}`;
    if (seen.has(id)) continue;
    seen.add(id);
    result.push({ document, domain });
  }
  return result;
}
