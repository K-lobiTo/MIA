// Memoria de la conversación (feature 014): qué vueltas anteriores se envían con cada pregunta y qué se le avisa a la
// persona. El historial vive solo en la memoria de la página, como la conversación; la API lo recorta y nunca lo guarda.
import type { HistoryTurn } from "../api/types";
import type { Exchange } from "./conversation";

// Máximos que acepta la API por vuelta; una respuesta más larga se envía recortada (la API la recorta más aún).
const MAX_ANSWER_CHARS = 20000;

/** Las últimas `turns` vueltas respondidas, de la más vieja a la más nueva. Las fallidas, las pendientes, las de sin
 * información y las de respuesta vacía no se envían ni ocupan lugar de la memoria. Con memoria 0 no se envía nada. */
export function buildHistory(exchanges: Exchange[], turns: number): HistoryTurn[] {
  if (!Number.isFinite(turns) || turns <= 0) return [];
  const answered = exchanges
    .filter((e) => e.status === "answered" && e.response !== undefined && e.response.answer.trim() !== "")
    .map((e) => ({
      question: e.question,
      answer: e.response!.answer.slice(0, MAX_ANSWER_CHARS),
      mode: e.response!.mode,
    }));
  return answered.slice(-Math.floor(turns));
}

/** El aviso de la memoria del artefacto ("" si no tiene). */
export function memoryNotice(turns: number): string {
  if (!Number.isFinite(turns) || turns <= 0) return "";
  if (turns === 1) return "Recuerda la última pregunta de esta conversación";
  return `Recuerda las últimas ${turns} preguntas de esta conversación`;
}
