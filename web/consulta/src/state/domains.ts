import type { Domain } from "../api/types";

const STORAGE_KEY = "mia-consulta-dominios";

export interface DomainGroup {
  /** Nombre de la unidad; nulo cuando todos los dominios son de una sola y no hace falta titular. */
  title: string | null;
  domains: Domain[];
}

const byName = (a: Domain, b: Domain) => a.name.localeCompare(b.name, "es");

/** Agrupa por unidad académica; con una sola unidad devuelve un grupo sin título (CON-1). */
export function groupByUnit(domains: Domain[]): DomainGroup[] {
  if (domains.length === 0) return [];
  const units = new Map<string, Domain[]>();
  const loose: Domain[] = [];
  for (const domain of domains) {
    if (domain.unit_name) units.set(domain.unit_name, [...(units.get(domain.unit_name) ?? []), domain]);
    else loose.push(domain);
  }
  if (units.size <= 1 && loose.length === 0) return [{ title: null, domains: [...domains].sort(byName) }];
  const groups: DomainGroup[] = [...units.entries()]
    .sort(([a], [b]) => a.localeCompare(b, "es"))
    .map(([title, list]) => ({ title, domains: list.sort(byName) }));
  if (loose.length) groups.push({ title: "Otros", domains: loose.sort(byName) });
  return groups;
}

/**
 * La selección guardada limitada a los dominios que siguen permitidos. Si nunca se guardó nada (null)
 * o ya no queda permitido ninguno de los guardados, se seleccionan todos; una lista guardada vacía
 * significa que se eligió ninguno y se respeta.
 */
export function restoreSelection(saved: string[] | null, domains: Domain[]): string[] {
  const all = domains.map((d) => d.id);
  if (saved === null) return all;
  if (saved.length === 0) return [];
  const allowed = new Set(all);
  const kept = saved.filter((id) => allowed.has(id));
  return kept.length > 0 ? kept : all;
}

// Almacenamiento: puede fallar o estar vacío (ventana privada, datos bloqueados).
export function loadSelection(): string[] | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw === null) return null;
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((id): id is string => typeof id === "string") : null;
  } catch {
    return null;
  }
}

export function saveSelection(ids: string[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(ids));
  } catch {
    // Sin almacenamiento disponible: la selección no se recuerda.
  }
}
