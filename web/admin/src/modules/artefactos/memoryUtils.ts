// Memoria de conversación de un artefacto (feature 014): cuántas vueltas (una pregunta y su respuesta) recuerda, de 0 a 10.
export const MAX_TURNS = 10;

export const MEMORY_HELP =
  "Cuántas preguntas y respuestas anteriores recuerda este artefacto en cada conversación. Con más memoria las preguntas de seguimiento ('¿y cuánto cuesta?') se entienden, pero cada consulta lleva más texto y cuesta más. 0 es el comportamiento de siempre.";

export type TurnsResult = { ok: true; value: number } | { ok: false; message: string };

/** Un entero de 0 a 10 escrito como texto. El servidor es quien hace cumplir el rango; esto evita enviar lo evidente. */
export function validateTurns(text: string): TurnsResult {
  const trimmed = text.trim();
  if (!/^\d+$/.test(trimmed) || Number(trimmed) > MAX_TURNS) {
    return { ok: false, message: `Escribe un número entero entre 0 y ${MAX_TURNS}.` };
  }
  return { ok: true, value: Number(trimmed) };
}

export function describeMemory(turns: number): string {
  if (turns <= 0) return "Sin memoria";
  return `Memoria: ${turns} ${turns === 1 ? "vuelta" : "vueltas"}`;
}
