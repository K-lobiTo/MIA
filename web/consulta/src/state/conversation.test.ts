import { describe, expect, it } from "vitest";
import type { QueryResponse } from "../api/types";
import { answeredExchange, failedExchange, formatLatency, newExchange, ratedExchange } from "./conversation";

const response = (no_info: boolean): QueryResponse => ({
  id: "q1",
  answer: "x",
  sources: [],
  mode: "literal",
  latency_ms: 1200,
  no_info,
});

describe("formatLatency", () => {
  it("usa una cifra decimal con coma bajo 10 segundos", () => {
    expect(formatLatency(3200)).toBe("3,2 s");
    expect(formatLatency(950)).toBe("0,9 s");
  });

  it("redondea a segundos enteros desde 10 segundos", () => {
    expect(formatLatency(10_400)).toBe("10 s");
    expect(formatLatency(41_600)).toBe("42 s");
  });
});

describe("transiciones de un intercambio", () => {
  it("nace pendiente con la pregunta, los dominios y el modo", () => {
    const e = newExchange("¿Cuántos?", ["a", "b"], "razonamiento");
    expect(e).toMatchObject({ status: "pending", question: "¿Cuántos?", domainIds: ["a", "b"], mode: "razonamiento" });
  });

  it("cada intercambio tiene un identificador local distinto", () => {
    expect(newExchange("a", [], "literal").localId).not.toBe(newExchange("a", [], "literal").localId);
  });

  it("una respuesta con información queda answered y sin información queda no_info", () => {
    const e = newExchange("p", ["a"], "literal");
    expect(answeredExchange(e, response(false)).status).toBe("answered");
    expect(answeredExchange(e, response(true)).status).toBe("no_info");
  });

  it("un error deja el intercambio failed con su mensaje", () => {
    const e = failedExchange(newExchange("p", ["a"], "literal"), { status: 502, message: "no disponible" });
    expect(e).toMatchObject({ status: "failed", error: { status: 502 } });
  });

  it("calificar guarda la calificación y el comentario, y una nueva reemplaza a la anterior", () => {
    const e = answeredExchange(newExchange("p", ["a"], "literal"), response(false));
    const primera = ratedExchange(e, "no_util", "incompleta");
    expect(primera).toMatchObject({ rating: "no_util", ratingComment: "incompleta" });
    expect(ratedExchange(primera, "util")).toMatchObject({ rating: "util", ratingComment: undefined });
  });
});
