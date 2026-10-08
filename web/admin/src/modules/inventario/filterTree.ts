import type { DomainNode, FolderNode, Inventory, UnitNode } from "../../api/types";

// Compara sin distinguir mayúsculas ni tildes ("curriculum" encuentra "Currículum").
export function normalize(text: string): string {
  return text.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase().trim();
}

function matches(name: string, query: string): boolean {
  return normalize(name).includes(query);
}

function filterFolder(folder: FolderNode, query: string): FolderNode | null {
  // Si la carpeta coincide por su nombre se muestra completa.
  if (matches(folder.name, query)) return folder;
  const folders = folder.folders.map((f) => filterFolder(f, query)).filter((f): f is FolderNode => f !== null);
  const documents = folder.documents.filter((d) => matches(d.filename, query));
  if (folders.length === 0 && documents.length === 0) return null;
  return { ...folder, folders, documents };
}

function filterDomain(domain: DomainNode, query: string): DomainNode | null {
  if (matches(domain.name, query)) return domain;
  const folders = domain.folders.map((f) => filterFolder(f, query)).filter((f): f is FolderNode => f !== null);
  const documents = domain.documents.filter((d) => matches(d.filename, query));
  if (folders.length === 0 && documents.length === 0) return null;
  return { ...domain, folders, documents };
}

function filterUnit(unit: UnitNode, query: string): UnitNode | null {
  if (matches(unit.name, query)) return unit;
  const domains = unit.domains.map((d) => filterDomain(d, query)).filter((d): d is DomainNode => d !== null);
  if (domains.length === 0) return null;
  return { ...unit, domains };
}

/** Deja las coincidencias por nombre de unidad, dominio, carpeta o documento y las ramas que las
 * contienen (INV-9). Un nodo que coincide se conserva con todo su contenido. */
export function filterInventory(inventory: Inventory, rawQuery: string): Inventory {
  const query = normalize(rawQuery);
  if (!query) return inventory;
  return {
    ...inventory,
    units: inventory.units.map((u) => filterUnit(u, query)).filter((u): u is UnitNode => u !== null),
    unassigned_domains: inventory.unassigned_domains
      .map((d) => filterDomain(d, query))
      .filter((d): d is DomainNode => d !== null),
  };
}
