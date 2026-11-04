import { describe, expect, it } from "vitest";
import type { QueryResponse } from "../api/types";
import type { Exchange } from "./conversation";
import { buildHistory, memoryNotice } from "./history";

function respuesta(answer: string, mode: "literal" | "razonamiento" = "literal", no_info = false): QueryResponse {
  return { id: "q", answer, sources: [], mode, latency_ms: 10, no_info };
}

function intercambio(n: number, status: Exchange["status"], response?: QueryResponse, mode: Exchange["mode"] = "literal"): Exchange {
  return { localId: `e${n}`, question: `pregunta ${n}`, domainIds: ["d"], mode, status, response };
}

describe("buildHistory", () => {
  const todos: Exchange[] = [
    intercambio(1, "answered", respuesta("respuesta 1")),
    intercambio(2, "answered", respuesta("respuesta 2", "razonamiento"), "razonamiento"),
    intercambio(3, "answered", respuesta("respuesta 3")),
  ];

  it("no envía nada con memoria 0", () => {
    expect(buildHistory(todos, 0)).toEqual([]);
  });

  it("toma las últimas vueltas respondidas, en orden, con su modo", () => {
    expect(buildHistory(todos, 2)).toEqual([
      { question: "pregunta 2", answer: "respuesta 2", mode: "razonamiento" },
      { question: "pregunta 3", answer: "respuesta 3", mode: "literal" },
    ]);
  });

  it("con menos vueltas que la memoria envía las que hay", () => {
    expect(buildHistory(todos, 10)).toHaveLength(3);
    expect(buildHistory([], 3)).toEqual([]);
  });

  it("omite las fallidas, las pendientes y las de sin información, sin importar dónde estén", () => {
    const mezcla: Exchange[] = [
      intercambio(1, "answered", respuesta("respuesta 1")),
      { ...intercambio(2, "failed"), error: { status: 502, message: "x" } },
      intercambio(3, "no_info", respuesta("No encontré información suficiente", "literal", true)),
      intercambio(4, "answered", respuesta("respuesta 4")),
      intercambio(5, "pending"),
    ];

    expect(buildHistory(mezcla, 5).map((v) => v.question)).toEqual(["pregunta 1", "pregunta 4"]);
    // Las vueltas excluidas no ocupan lugar de la memoria.
    expect(buildHistory(mezcla, 1).map((v) => v.question)).toEqual(["pregunta 4"]);
  });

  it("omite una respuesta vacía", () => {
    expect(buildHistory([intercambio(1, "answered", respuesta("   "))], 3)).toEqual([]);
  });
});

describe("memoryNotice", () => {
  it("avisa cuántas preguntas recuerda y no dice nada con 0", () => {
    expect(memoryNotice(0)).toBe("");
    expect(memoryNotice(1)).toBe("Recuerda la última pregunta de esta conversación");
    expect(memoryNotice(4)).toBe("Recuerda las últimas 4 preguntas de esta conversación");
  });
});

describe("buildHistory: tamaño", () => {
  it("recorta una respuesta más larga que el máximo que acepta la API", () => {
    const larga = "a".repeat(25000);
    const historial = buildHistory([intercambio(1, "answered", respuesta(larga))], 1);

    expect(historial[0].answer).toHaveLength(20000);
  });
});
