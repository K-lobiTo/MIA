export const ALLOWED_IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg"];
export const ALLOWED_IMAGE_TYPES = ["image/png", "image/jpeg"];
// Largo máximo de la descripción de una imagen (la API lo hace cumplir).
export const MAX_CAPTION = 1000;

/** Advertencia que se muestra al subir una imagen: la ruta que la sirve es pública (IMG-4 y FR-033). */
export const PUBLIC_IMAGE_WARNING =
  "Las imágenes son públicas: cualquiera que tenga el enlace puede verlas. Sube solo lo que pueda ver cualquiera.";

/** Mensaje de rechazo si la imagen no se puede subir (formato o tamaño), o null si es válida (IMG-2). La API vuelve a
 * comprobarlo por el contenido del archivo; esto solo evita subir lo que se sabe que será rechazado. */
export function validateImageFile(file: { name: string; size: number; type?: string }, maxMb: number): string | null {
  const lower = file.name.toLowerCase();
  const extensionOk = ALLOWED_IMAGE_EXTENSIONS.some((extension) => lower.endsWith(extension));
  const typeOk = !file.type || ALLOWED_IMAGE_TYPES.includes(file.type);
  if (!extensionOk || !typeOk) return "Solo se aceptan imágenes PNG o JPG.";
  if (file.size > maxMb * 1024 * 1024) return `Supera el tamaño máximo de ${maxMb} MB.`;
  return null;
}

/** El orden de los ids tras mover el de `index` una posición (`-1` sube, `1` baja). Igual si ya está en el borde. */
export function moveImage(ids: string[], index: number, delta: -1 | 1): string[] {
  const target = index + delta;
  if (index < 0 || index >= ids.length || target < 0 || target >= ids.length) return ids;
  const next = [...ids];
  [next[index], next[target]] = [next[target], next[index]];
  return next;
}

/** La dirección completa de una imagen: la ruta relativa de la API (`/media/...`) con la dirección de la API delante. */
export function mediaUrl(apiBase: string, path: string): string {
  return `${apiBase.replace(/\/+$/, "")}${path.startsWith("/") ? path : `/${path}`}`;
}

export function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1).replace(".", ",")} MB`;
}
