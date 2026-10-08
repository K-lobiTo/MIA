import type { DomainNode, FolderNode, Inventory } from "../../api/types";

export const ALLOWED_EXTENSIONS = [".pdf", ".docx", ".txt"];

function folderHasPending(folder: FolderNode): boolean {
  return folder.documents.some(isInProgress) || folder.folders.some(folderHasPending);
}

function domainHasPending(domain: DomainNode): boolean {
  return domain.documents.some(isInProgress) || domain.folders.some(folderHasPending);
}

function isInProgress(document: { status: string }): boolean {
  return document.status === "pending" || document.status === "processing";
}

/** Hay documentos en cola o procesando: el panel sigue consultando hasta que terminen (INV-5). */
export function hasPendingDocuments(inventory: Inventory | undefined): boolean {
  if (!inventory) return false;
  return (
    inventory.units.some((unit) => unit.domains.some(domainHasPending)) ||
    inventory.unassigned_domains.some(domainHasPending)
  );
}

/** Mensaje de rechazo si el archivo no se puede subir (tipo o tamaño), o null si es válido (INV-4). */
export function validateFile(file: { name: string; size: number }, maxMb: number): string | null {
  const lower = file.name.toLowerCase();
  if (!ALLOWED_EXTENSIONS.some((extension) => lower.endsWith(extension))) {
    return "Solo se aceptan archivos PDF, DOCX y TXT.";
  }
  if (file.size > maxMb * 1024 * 1024) {
    return `Supera el tamaño máximo de ${maxMb} MB.`;
  }
  return null;
}
