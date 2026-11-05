import { describe, expect, it } from "vitest";
import type { QueryResponse } from "../api/types";
import type { Exchange } from "./conversation";
import { authErrorMessage, classifyAuthError, askPayload, authScreen, chatErrorAction, exchangesFromConversation, lockMessage } from "./chat";

describe("classifyAuthError", () => {
  it("distingue la sesión inválida, la que se exige y la clave inválida", () => {
    expect(classifyAuthError(401, "session_invalid")).toBe("session_invalid");
    expect(classifyAuthError(401, "login_required")).toBe("login_required");
    // Un 401 sin código sigue siendo la clave del artefacto, como antes de la feature.
    expect(classifyAuthError(401, undefined)).toBe("invalid_key");
    expect(classifyAuthError(401, "algo_raro")).toBe("invalid_key");
  });

  it("cualquier otro estado no es un error de sesión", () => {
    expect(classifyAuthError(403, "session_invalid")).toBe("other");
    expect(classifyAuthError(429, "too_many_attempts")).toBe("other");
    expect(classifyAuthError(500, undefined)).toBe("other");
    expect(classifyAuthError(0, undefined)).toBe("other");
  });
});

describe("authErrorMessage", () => {
  it("da los mensajes en español del contrato", () => {
    expect(authErrorMessage("invalid_credentials")).toBe("Usuario o contraseña incorrectos.");
    expect(authErrorMessage("session_invalid")).toBe("Tu sesión venció. Inicia sesión de nuevo.");
    expect(authErrorMessage("login_required")).toBe("Esta Consulta exige iniciar sesión para preguntar.");
    expect(authErrorMessage("otro")).toBeNull();
    expect(authErrorMessage(undefined)).toBeNull();
  });
});

describe("lockMessage", () => {
  it("redondea la espera a minutos hacia arriba", () => {
    expect(lockMessage(900)).toBe("Demasiados intentos. Espera 15 minutos e intenta de nuevo.");
    expect(lockMessage(61)).toBe("Demasiados intentos. Espera 2 minutos e intenta de nuevo.");
    expect(lockMessage(30)).toBe("Demasiados intentos. Espera 1 minuto e intenta de nuevo.");
    expect(lockMessage(undefined)).toBe("Demasiados intentos. Espera unos minutos e intenta de nuevo.");
  });
});

describe("exchangesFromConversation", () => {
  const guardada = {
    id: "c1",
    title: "¿Cuándo empieza?",
    created_at: "2026-11-04T10:00:00Z",
    updated_at: "2026-11-04T10:05:00Z",
    turns: [
      {
        position: 2,
        question: "¿y cuánto cuesta?",
        answer: "No encontré información suficiente",
        sources: [],
        mode: "literal" as const,
        no_info: true,
        created_at: "2026-11-04T10:05:00Z",
      },
      {
        position: 1,
        question: "¿Cuándo empieza?",
        answer: "Inicia el I trimestre de 2027.",
        sources: [{ domain: "Admisión", document: "Ciber_Admision.txt" }],
        mode: "razonamiento" as const,
        no_info: false,
        created_at: "2026-11-04T10:00:00Z",
      },
    ],
  };

  it("convierte cada vuelta guardada en una vuelta ya respondida, en orden, marcada como guardada", () => {
    const vueltas = exchangesFromConversation(guardada);

    expect(vueltas.map((v) => v.question)).toEqual(["¿Cuándo empieza?", "¿y cuánto cuesta?"]);
    expect(vueltas.map((v) => v.status)).toEqual(["answered", "no_info"]);
    expect(vueltas.every((v) => v.stored === true)).toBe(true);
    expect(vueltas[0].mode).toBe("razonamiento");
    expect(vueltas[0].response?.answer).toBe("Inicia el I trimestre de 2027.");
  });

  it("las fuentes conservan dominio y documento y no inventan el fragmento", () => {
    const [primera] = exchangesFromConversation(guardada);

    expect(primera.response?.sources).toEqual([
      { domain: "Admisión", document: "Ciber_Admision.txt", excerpt: "" },
    ]);
    expect(primera.response?.id).toBe("");
  });

  it("cada vuelta tiene un identificador propio y estable", () => {
    const ids = exchangesFromConversation(guardada).map((v) => v.localId);
    expect(new Set(ids).size).toBe(2);
    expect(exchangesFromConversation(guardada).map((v) => v.localId)).toEqual(ids);
  });
});


describe("askPayload", () => {
  const respondida = (n: number): Exchange => ({
    localId: `e${n}`,
    question: `pregunta ${n}`,
    domainIds: ["d"],
    mode: "literal",
    status: "answered",
    response: { id: "q", answer: `respuesta ${n}`, sources: [], mode: "literal", latency_ms: 10, no_info: false } as QueryResponse,
  });
  const base = { hasSession: false, chatEnabled: true, conversationId: null, exchanges: [respondida(1), respondida(2)], memoryTurns: 2 };

  it("con sesión y guardado activo envía solo el identificador de la conversación, nunca el historial", () => {
    expect(askPayload({ ...base, hasSession: true, conversationId: "c1" })).toEqual({ conversation_id: "c1" });
  });

  it("con sesión y sin conversación todavía (la primera pregunta) no envía nada", () => {
    expect(askPayload({ ...base, hasSession: true })).toEqual({});
  });

  it("sin sesión envía el historial de la página como en la feature 014", () => {
    expect(askPayload(base)).toEqual({
      history: [
        { question: "pregunta 1", answer: "respuesta 1", mode: "literal" },
        { question: "pregunta 2", answer: "respuesta 2", mode: "literal" },
      ],
    });
  });

  it("con sesión pero el guardado apagado también envía el historial de la página", () => {
    const payload = askPayload({ ...base, hasSession: true, chatEnabled: false, conversationId: "c1" });
    expect(payload.conversation_id).toBeUndefined();
    expect(payload.history).toHaveLength(2);
  });

  it("con memoria 0 no envía historial", () => {
    expect(askPayload({ ...base, memoryTurns: 0 })).toEqual({});
  });
});

describe("chatErrorAction", () => {
  it("una conversación que ya no existe (404) pide empezar otra y devuelve el texto al campo", () => {
    expect(chatErrorAction(404, undefined, true)).toEqual({
      message: "Esa conversación ya no existe.",
      newConversation: true,
    });
  });

  it("un 404 sin conversación abierta no es de este tipo", () => {
    expect(chatErrorAction(404, undefined, false)).toBeNull();
  });

  it("los dos 409 explican el límite y no cambian de conversación", () => {
    expect(chatErrorAction(409, "conversation_full", true)).toEqual({
      message: "Esta conversación llegó al máximo de preguntas. Empieza una nueva.",
      newConversation: false,
    });
    expect(chatErrorAction(409, "too_many_conversations", false)).toEqual({
      message: "Llegaste al máximo de conversaciones guardadas. Borra alguna para empezar otra.",
      newConversation: false,
    });
    expect(chatErrorAction(409, "otro", true)).toBeNull();
  });

  it("la sesión vencida y la sesión exigida también devuelven el texto al campo con su mensaje", () => {
    expect(chatErrorAction(401, "session_invalid", false)?.message).toBe("Tu sesión venció. Inicia sesión de nuevo.");
    expect(chatErrorAction(401, "login_required", false)?.message).toBe("Esta Consulta exige iniciar sesión para preguntar.");
  });

  it("un 401 sin código (clave inválida) y los demás errores no son de este tipo", () => {
    expect(chatErrorAction(401, undefined, true)).toBeNull();
    expect(chatErrorAction(500, undefined, true)).toBeNull();
    expect(chatErrorAction(0, undefined, true)).toBeNull();
  });
});


describe("authScreen", () => {
  const base = { hasKey: true, hasSession: false, requireLogin: false, loginRequested: false };

  it("sin clave pide la clave, aunque haya sesión", () => {
    expect(authScreen({ ...base, hasKey: false })).toBe("key");
    expect(authScreen({ ...base, hasKey: false, hasSession: true, requireLogin: true })).toBe("key");
  });

  it("con clave, sin sesión y un artefacto que no la exige, la Consulta funciona como siempre", () => {
    expect(authScreen(base)).toBe("app");
  });

  it("con clave fija (hay clave sin pedirla) el inicio de sesión es solo una opción que la persona abre", () => {
    expect(authScreen({ ...base, loginRequested: true })).toBe("login");
    expect(authScreen({ ...base, loginRequested: true, hasSession: true })).toBe("app");
  });

  it("si el artefacto exige sesión y no hay, el inicio de sesión sustituye a la Consulta", () => {
    expect(authScreen({ ...base, requireLogin: true })).toBe("login_required");
    expect(authScreen({ ...base, requireLogin: true, loginRequested: true })).toBe("login_required");
  });

  it("con sesión, aunque el artefacto la exija, se entra a la Consulta", () => {
    expect(authScreen({ ...base, requireLogin: true, hasSession: true })).toBe("app");
  });
});
