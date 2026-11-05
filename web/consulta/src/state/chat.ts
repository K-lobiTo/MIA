// Usuarios e historial de chats de la Consulta (feature 015): funciones puras de sesión y de conversaciones guardadas.
import type { HistoryTurn, StoredConversation } from "../api/types";
import type { Exchange } from "./conversation";
import { buildHistory } from "./history";

export type AuthErrorKind = "session_invalid" | "login_required" | "invalid_key" | "other";

/** Qué clase de rechazo es una respuesta 401. Antes de la feature todo 401 era "clave inválida": ahora la API distingue
 * la sesión por un `code`, y un 401 sin código (o con uno desconocido) sigue siendo la clave del artefacto. */
export function classifyAuthError(status: number, code: string | undefined): AuthErrorKind {
  if (status !== 401) return "other";
  if (code === "session_invalid") return "session_invalid";
  if (code === "login_required") return "login_required";
  return "invalid_key";
}

const MESSAGES: Record<string, string> = {
  invalid_credentials: "Usuario o contraseña incorrectos.",
  session_invalid: "Tu sesión venció. Inicia sesión de nuevo.",
  login_required: "Esta Consulta exige iniciar sesión para preguntar.",
};

export function authErrorMessage(code: string | undefined): string | null {
  return code !== undefined ? (MESSAGES[code] ?? null) : null;
}

/** El aviso de espera tras demasiados intentos, con los segundos de `Retry-After` redondeados a minutos hacia arriba. */
export function lockMessage(retryAfterSeconds: number | undefined): string {
  if (retryAfterSeconds === undefined || !Number.isFinite(retryAfterSeconds) || retryAfterSeconds <= 0) {
    return "Demasiados intentos. Espera unos minutos e intenta de nuevo.";
  }
  const minutes = Math.max(1, Math.ceil(retryAfterSeconds / 60));
  return `Demasiados intentos. Espera ${minutes} ${minutes === 1 ? "minuto" : "minutos"} e intenta de nuevo.`;
}

/** Las vueltas de una conversación guardada como vueltas ya respondidas de la pantalla. Lo guardado no trae el tiempo de
 * respuesta, el identificador de la consulta ni el fragmento de cada fuente, así que la vuelta se marca `stored`. */
export function exchangesFromConversation(conversation: StoredConversation): Exchange[] {
  return [...conversation.turns]
    .sort((a, b) => a.position - b.position)
    .map((turn) => ({
      localId: `s-${conversation.id}-${turn.position}`,
      question: turn.question,
      domainIds: [],
      mode: turn.mode,
      status: turn.no_info ? ("no_info" as const) : ("answered" as const),
      stored: true,
      response: {
        id: "",
        answer: turn.answer,
        sources: turn.sources.map((source) => ({ ...source, excerpt: "" })),
        mode: turn.mode,
        latency_ms: 0,
        no_info: turn.no_info,
      },
    }));
}

export interface AskContext {
  /** Hay una persona con la sesión abierta. */
  hasSession: boolean;
  /** El servidor guarda conversaciones (`GET /config`: `chat.enabled`). */
  chatEnabled: boolean;
  /** La conversación guardada abierta, si la hay. */
  conversationId: string | null;
  exchanges: Exchange[];
  /** Vueltas que recuerda el artefacto (feature 014). */
  memoryTurns: number;
}

/** Qué viaja con la pregunta para que se entienda un seguimiento: con sesión y guardado activo solo el identificador de la
 * conversación (el servidor carga el historial de lo guardado); en cualquier otro caso el historial de la página, como en la
 * feature 014. */
export function askPayload(context: AskContext): { history?: HistoryTurn[]; conversation_id?: string } {
  if (context.hasSession && context.chatEnabled) {
    return context.conversationId ? { conversation_id: context.conversationId } : {};
  }
  const history = buildHistory(context.exchanges, context.memoryTurns);
  return history.length > 0 ? { history } : {};
}

export interface ChatErrorAction {
  /** Lo que se le dice a la persona; la pregunta escrita vuelve al campo para no perderla. */
  message: string;
  /** La conversación abierta ya no existe: la siguiente pregunta empieza una nueva. */
  newConversation: boolean;
}

/** Cómo se atiende un rechazo de `POST /query` que tiene que ver con la sesión o con la conversación guardada: la sesión
 * vencida o exigida, la conversación que ya no existe (404, p. ej. se borró en otra pestaña) y los dos límites (409). Para
 * cualquier otro error devuelve null y se sigue con el manejo de siempre. */
export function chatErrorAction(status: number, code: string | undefined, hadConversation: boolean): ChatErrorAction | null {
  const kind = classifyAuthError(status, code);
  if (kind === "session_invalid" || kind === "login_required") {
    return { message: authErrorMessage(kind) ?? "Inicia sesión para continuar.", newConversation: false };
  }
  if (status === 404 && hadConversation) return { message: "Esa conversación ya no existe.", newConversation: true };
  if (status === 409 && code === "conversation_full") {
    return { message: "Esta conversación llegó al máximo de preguntas. Empieza una nueva.", newConversation: false };
  }
  if (status === 409 && code === "too_many_conversations") {
    return {
      message: "Llegaste al máximo de conversaciones guardadas. Borra alguna para empezar otra.",
      newConversation: false,
    };
  }
  return null;
}

export type AuthScreen = "key" | "login_required" | "login" | "app";

export interface AuthScreenInput {
  /** Hay una clave de artefacto (guardada, escrita o fija de la instancia). */
  hasKey: boolean;
  /** Hay una persona con la sesión abierta. */
  hasSession: boolean;
  /** El artefacto exige iniciar sesión para consultar (`GET /config`: `artifact.require_login`). */
  requireLogin: boolean;
  /** La persona pidió iniciar sesión (botón o sesión vencida). */
  loginRequested: boolean;
}

/** Qué pantalla mostrar. Sin clave se pide la clave (como siempre; con clave fija esa pantalla nunca aparece). Si el
 * artefacto exige sesión y no hay, el inicio de sesión sustituye a la Consulta. Si no la exige, el inicio de sesión es
 * opcional: solo aparece si la persona lo pidió. Con todo en orden, la Consulta. */
export function authScreen(input: AuthScreenInput): AuthScreen {
  if (!input.hasKey) return "key";
  if (input.hasSession) return "app";
  if (input.requireLogin) return "login_required";
  return input.loginRequested ? "login" : "app";
}

