// Prompt propio de un artefacto: un texto adicional que se anexa a la instrucción del modo de respuesta.
export const MAX_PROMPT_CHARS = 4000;

export const PROMPT_LABEL = "Instrucciones propias del artefacto (opcional)";

export const PROMPT_HELP =
  "Se suman a las instrucciones del modo de respuesta, no las reemplazan: el artefacto sigue respondiendo solo con los documentos. Sirven para ajustar el enfoque, por ejemplo centrarse en la información del propio programa. Rigen desde la consulta siguiente. Vacío es el comportamiento de siempre.";

export function validatePrompt(text: string): string | null {
  return text.length > MAX_PROMPT_CHARS ? `Máximo ${MAX_PROMPT_CHARS} caracteres (van ${text.length}).` : null;
}

export function describePrompt(prompt: string): string {
  const length = prompt.trim().length;
  return length === 0 ? "Las de siempre" : `Propias (${length} caracteres)`;
}
