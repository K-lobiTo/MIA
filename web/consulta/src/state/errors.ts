import type { ModeId } from "../api/types";
import type { ExchangeError } from "./conversation";
import { TEMPLATE_GONE } from "./templates";

export interface ErrorView {
  message: string;
  /** Se puede reintentar la misma pregunta tal cual. */
  canRetry: boolean;
  /** Se ofrece reintentarla en modo literal (solo si falló un modo con razonamiento o plantilla). */
  offerLiteral: boolean;
}

/** Mensaje y salidas de un error al preguntar (CON-7), según la tabla de contracts/ui-consulta.md. */
export function describeError(error: ExchangeError, mode: ModeId, literalAvailable = true): ErrorView {
  const literalFallback = mode !== "literal" && literalAvailable;
  switch (error.status) {
    case 0:
      return { message: "No se pudo conectar con MIA. Revisa tu conexión.", canRetry: true, offerLiteral: false };
    case -1:
      return { message: "MIA tardó demasiado en responder.", canRetry: true, offerLiteral: literalFallback };
    case 502:
      return {
        message: "El modelo de lenguaje no está disponible en este momento.",
        canRetry: true,
        offerLiteral: literalFallback,
      };
    case 429:
      return { message: error.message, canRetry: false, offerLiteral: literalFallback };
    case 403:
      if (error.message.toLowerCase().includes("desactivado")) {
        return {
          message: `${error.message} Comunícate con quien administra MIA.`,
          canRetry: false,
          offerLiteral: false,
        };
      }
      return { message: error.message, canRetry: true, offerLiteral: false };
    default:
      return { message: `Error ${error.status}: ${error.message}`, canRetry: true, offerLiteral: false };
  }
}

export interface TemplateGoneAction {
  /** Lo que se le dice a la persona; el texto escrito vuelve al campo para no perderlo. */
  message: string;
  /** Se olvida la plantilla elegida y se vuelve a pedir la lista de plantillas. */
  forgetTemplate: true;
}

/** Cómo se atiende un rechazo de `POST /query` porque la plantilla elegida ya no está disponible (se eliminó o no es de esa
 * persona, feature 020): un `404` con el mensaje fijo de la API. Se distingue del `404` de una conversación que ya no existe
 * por su mensaje, así que se evalúa primero. Para cualquier otro error devuelve null. */
export function templateGoneAction(status: number, message: string): TemplateGoneAction | null {
  if (status !== 404 || message !== TEMPLATE_GONE) return null;
  return { message: `${TEMPLATE_GONE} Elige otra.`, forgetTemplate: true };
}
