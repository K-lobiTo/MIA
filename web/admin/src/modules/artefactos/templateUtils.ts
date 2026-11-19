// Plantillas del modo plantilla (feature 020): validación del formulario con los mismos límites y mensajes que la API.
export const NAME_MAX_CHARS = 80;

export const MANAGE_WARNING = "No incluyas datos personales ni información confidencial: la plantilla se guarda tal cual.";

export const TEMPLATE_HELP =
  "Una plantilla es la estructura de la respuesta (sus secciones, títulos y orden). Los datos salen siempre de los documentos: la plantilla solo da la forma.";

export interface TemplateFormErrors {
  name: string | null;
  content: string | null;
}

/** Valida el nombre y el contenido con las reglas de la API; `null` en cada campo válido. */
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

/** Texto de la cantidad de plantillas de un artefacto para su botón. */
export function describeTemplateCount(count: number): string {
  return count === 0 ? "Plantillas" : `Plantillas (${count})`;
}
