import type { ExchangeError } from "./conversation";

export const INVALID_QUESTION_MESSAGE = "La pregunta no es válida (máximo 2000 caracteres).";

export interface Rejection {
  /** Texto que vuelve al campo de pregunta para que no se pierda lo escrito. */
  restore: string;
  message: string;
}

/** Una pregunta que la API rechaza por su contenido (422) no es una respuesta fallida: se devuelve al campo. */
export function rejectionOf(error: ExchangeError, question: string): Rejection | null {
  if (error.status !== 422) return null;
  return { restore: question, message: INVALID_QUESTION_MESSAGE };
}
