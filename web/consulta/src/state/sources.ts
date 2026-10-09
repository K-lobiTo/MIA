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

export const EXCERPT_PREVIEW_CHARS = 260;

export interface ExcerptPreview {
  text: string;
  /** El fragmento tiene más texto del que se muestra: se ofrece "Ver más". */
  truncated: boolean;
}

/** Texto de un fragmento en una sola línea; si es largo, solo el comienzo, cortado en una palabra completa. */
export function previewExcerpt(excerpt: string, max = EXCERPT_PREVIEW_CHARS): ExcerptPreview {
  const clean = excerpt.replace(/\s+/g, " ").trim();
  if (clean.length <= max) return { text: clean, truncated: false };
  const cut = clean.slice(0, max);
  const lastSpace = cut.lastIndexOf(" ");
  return { text: `${(lastSpace > max * 0.6 ? cut.slice(0, lastSpace) : cut).trimEnd()}…`, truncated: true };
}
