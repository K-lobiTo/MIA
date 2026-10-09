// La conversación vive solo en la memoria de la página: no se guarda en el navegador (FR-020), porque
// las preguntas pueden contener datos personales. El registro completo queda en la API.
import type { ModeId, QueryResponse, Rating } from "../api/types";

export type ExchangeStatus = "pending" | "answered" | "no_info" | "failed";

export interface ExchangeError {
  /** Estado HTTP; 0 sin conexión, -1 tiempo agotado. */
  status: number;
  message: string;
}

export interface Exchange {
  localId: string;
  question: string;
  domainIds: string[];
  mode: ModeId;
  status: ExchangeStatus;
  response?: QueryResponse;
  error?: ExchangeError;
  rating?: Rating;
  ratingComment?: string;
}

let counter = 0;

export function newExchange(question: string, domainIds: string[], mode: ModeId): Exchange {
  counter += 1;
  return { localId: `e${counter}`, question, domainIds, mode, status: "pending" };
}

export function answeredExchange(exchange: Exchange, response: QueryResponse): Exchange {
  return { ...exchange, status: response.no_info ? "no_info" : "answered", response };
}

export function failedExchange(exchange: Exchange, error: ExchangeError): Exchange {
  return { ...exchange, status: "failed", error };
}

export function ratedExchange(exchange: Exchange, rating: Rating, comment?: string): Exchange {
  return { ...exchange, rating, ratingComment: comment };
}

/** Tiempo de respuesta para el pie de cada respuesta: "3,2 s" bajo 10 s y "41 s" desde 10 s. */
export function formatLatency(ms: number): string {
  const seconds = ms / 1000;
  if (seconds < 10) return `${seconds.toFixed(1).replace(".", ",")} s`;
  return `${Math.round(seconds)} s`;
}
