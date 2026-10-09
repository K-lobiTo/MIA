import type { ModeId } from "../api/types";
import type { ExchangeError } from "./conversation";

export interface ErrorView {
  message: string;
  /** Se puede reintentar la misma pregunta tal cual. */
  canRetry: boolean;
  /** Se ofrece reintentarla en modo literal (solo si falló un modo con razonamiento). */
  offerLiteral: boolean;
}

/** Mensaje y salidas de un error al preguntar (CON-7), según la tabla de contracts/ui-consulta.md. */
export function describeError(error: ExchangeError, mode: ModeId, literalAvailable = true): ErrorView {
  const literalFallback = mode === "razonamiento" && literalAvailable;
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
