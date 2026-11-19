// Plantillas del modo plantilla (feature 020): cuál se eligió y si se puede preguntar. La plantilla elegida se recuerda por
// artefacto en el navegador, como el modo; la API valida siempre que siga disponible.
import type { ModeId, Template, TemplatesResponse } from "../api/types";

export const PICK_TEMPLATE = "Elige una plantilla.";
export const TEMPLATE_GONE = "La plantilla ya no está disponible.";

/** Un ejemplo breve de cómo escribir una plantilla, para quien aún no tiene ninguna. */
export const TEMPLATE_EXAMPLE = "Resumen: qué es el programa en dos frases.\nRequisitos: lo que se pide para ingresar.\nCostos: cuánto cuesta.";

const STORAGE_PREFIX = "mia-consulta-plantilla:";

// Almacenamiento: puede fallar o estar vacío (ventana privada, datos bloqueados).
export function loadTemplateId(artifactKey: string): string | null {
  try {
    return localStorage.getItem(STORAGE_PREFIX + artifactKey);
  } catch {
    return null;
  }
}

export function saveTemplateId(artifactKey: string, id: string | null): void {
  try {
    if (id) localStorage.setItem(STORAGE_PREFIX + artifactKey, id);
    else localStorage.removeItem(STORAGE_PREFIX + artifactKey);
  } catch {
    // Sin almacenamiento disponible: la plantilla no se recuerda.
  }
}

export interface TemplateSelection {
  /** La plantilla con la que se preguntaría: la elegida si todavía está en la lista, si no ninguna. */
  template: Template | null;
  /** Por qué no se puede enviar (modo plantilla sin plantilla elegida), o nulo. */
  blocked: string | null;
}

/** Todas las plantillas que se pueden elegir: primero las del artefacto y luego las personales. */
export function allTemplates(data: TemplatesResponse | undefined): Template[] {
  return data ? [...data.artifact, ...data.mine] : [];
}

/** La plantilla efectiva y el motivo de bloqueo: con el modo plantilla elegido y sin plantilla disponible no se envía. */
export function resolveTemplateSelection(
  mode: ModeId,
  data: TemplatesResponse | undefined,
  savedId: string | null,
): TemplateSelection {
  const template = allTemplates(data).find((t) => t.id === savedId) ?? null;
  return { template, blocked: mode === "plantilla" && template === null ? PICK_TEMPLATE : null };
}

export const NAME_MAX_CHARS = 80;
export const MANAGE_WARNING = "No incluyas datos personales ni información confidencial: la plantilla se guarda tal cual.";
export const LOGIN_NOTICE = "Inicia sesión para guardar tus propias plantillas.";

export interface TemplateFormErrors {
  name: string | null;
  content: string | null;
}

/** Valida el nombre y el contenido con las mismas reglas y mensajes que la API; `null` en cada campo válido. */
export function validateTemplateForm(name: string, content: string, maxChars: number): TemplateFormErrors {
  const cleanName = name.trim();
  let nameError: string | null = null;
  if (cleanName === "") nameError = "El nombre no puede estar vacío.";
  else if (/[\r\n]/.test(cleanName)) nameError = "El nombre no puede tener saltos de línea.";
  else if (cleanName.length > NAME_MAX_CHARS) nameError = `El nombre no puede superar ${NAME_MAX_CHARS} caracteres.`;

  const cleanContent = content.trim();
  let contentError: string | null = null;
  if (cleanContent === "") contentError = "El contenido no puede estar vacío.";
  else if (cleanContent.length > maxChars) contentError = `El contenido no puede superar ${maxChars} caracteres.`;
  return { name: nameError, content: contentError };
}

export function templateFormValid(errors: TemplateFormErrors): boolean {
  return errors.name === null && errors.content === null;
}

export const SCOPE_LABEL = { artifact: "Solo para este artefacto", all: "Para todos mis artefactos" } as const;

export interface RestoredTemplate {
  /** La plantilla que queda seleccionada al retomar la conversación, o nulo si ya no está disponible. */
  selectedId: string | null;
  /** Qué se le dice a la persona cuando hay que elegir otra, o nulo. */
  notice: string | null;
}

/** Al retomar una conversación guardada: la plantilla que usó queda seleccionada si sigue en la lista actual (con su versión
 * actual, que siempre viene de la API); si se eliminó o ya no está disponible se pide elegir otra, nombrando la anterior. */
export function restoreTemplate(
  remembered: { id: string; name: string } | null,
  data: TemplatesResponse | undefined,
): RestoredTemplate {
  if (remembered === null) return { selectedId: null, notice: null };
  if (allTemplates(data).some((t) => t.id === remembered.id)) return { selectedId: remembered.id, notice: null };
  const label = remembered.name ? `La plantilla "${remembered.name}"` : "La plantilla de esta conversación";
  return { selectedId: null, notice: `${label} ya no está disponible. Elige otra.` };
}
