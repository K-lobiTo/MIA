import type { DomainNode, FolderNode, Inventory } from "../../api/types";

export const ALLOWED_EXTENSIONS = [".pdf", ".docx", ".txt", ".xlsx", ".csv"];

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
    return "Solo se aceptan archivos PDF, DOCX, TXT, XLSX y CSV.";
  }
  if (file.size > maxMb * 1024 * 1024) {
    return `Supera el tamaño máximo de ${maxMb} MB.`;
  }
  return null;
}

/** Aviso de datos personales al elegir un CSV (feature 021): un CSV suele ser una lista de personas. */
export const CSV_NOTICE =
  "Los archivos CSV suelen traer datos de personas (cédulas, correos, teléfonos, direcciones). Lo que subas se podrá consultar con los artefactos que tengan acceso a este dominio: quita o anonimiza esas columnas antes de subirlo si no hacen falta.";

/** Si entre los archivos elegidos o soltados hay al menos un CSV (por su extensión, sin importar mayúsculas). */
export function hasCsv(files: { name: string }[]): boolean {
  return files.some((file) => file.name.toLowerCase().endsWith(".csv"));
}

/** Aviso de la ventana "Agregar página web" (feature 022): el texto de una página puede traer nombres y contactos. */
export const WEB_NOTICE =
  "El contenido de la página se podrá consultar con los artefactos de este dominio. MIA no filtra datos personales (nombres, correos y teléfonos de contactos): revisa el texto una vez agregado y elimina el documento si no es adecuado.";

/** Mensaje si la dirección está vacía, o null. La validación real (esquema, red interna, largo) es de la API. */
export function validarDireccion(texto: string): string | null {
  return texto.trim() === "" ? "Escribe la dirección de la página." : null;
}

export type ResultadoDeAgregar = { ok: true; yaExistia: boolean } | { ok: false; code?: string };

/** La ventana se cierra sola solo cuando la página se agregó de verdad: un rechazo o una página que ya estaba se muestran en ella. */
export function debeCerrar(resultado: ResultadoDeAgregar): boolean {
  return resultado.ok && !resultado.yaExistia;
}

/** La dirección de un documento web solo se usa como enlace si es http o https (nunca `javascript:` ni `data:`). */
export function enlaceSeguro(direccion: string | null | undefined): string | null {
  return direccion && /^https?:\/\//i.test(direccion) ? direccion : null;
}
