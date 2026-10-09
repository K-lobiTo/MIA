import { describe, expect, it } from "vitest";
import { previewExcerpt, uniqueDocuments } from "./sources";

const source = (document: string, domain: string, excerpt = "...") => ({ document, domain, excerpt });

describe("uniqueDocuments", () => {
  it("devuelve cada documento una sola vez, en el orden en que aparece", () => {
    expect(
      uniqueDocuments([source("a.pdf", "Currículum"), source("b.pdf", "Currículum"), source("a.pdf", "Currículum", "otro")]),
    ).toEqual([
      { document: "a.pdf", domain: "Currículum" },
      { document: "b.pdf", domain: "Currículum" },
    ]);
  });

  it("un mismo nombre en dominios distintos cuenta como documentos distintos", () => {
    expect(uniqueDocuments([source("acta.pdf", "Computación"), source("acta.pdf", "Administración")])).toHaveLength(2);
  });

  it("sin fuentes devuelve una lista vacía", () => {
    expect(uniqueDocuments([])).toEqual([]);
  });
});

describe("previewExcerpt", () => {
  it("un fragmento corto se muestra completo, en una sola línea", () => {
    expect(previewExcerpt("Créditos:\n  4\n\nHoras: 14")).toEqual({ text: "Créditos: 4 Horas: 14", truncated: false });
  });

  it("un fragmento largo se corta en una palabra completa y se marca como truncado", () => {
    const largo = "palabra ".repeat(100).trim();
    const vista = previewExcerpt(largo, 50);
    expect(vista.truncated).toBe(true);
    expect(vista.text.endsWith("…")).toBe(true);
    expect(vista.text.length).toBeLessThanOrEqual(51);
    expect(vista.text.slice(0, -1).split(" ").every((p) => p === "palabra")).toBe(true);
  });

  it("un texto largo sin espacios se corta igual", () => {
    expect(previewExcerpt("x".repeat(100), 20)).toEqual({ text: `${"x".repeat(20)}…`, truncated: true });
  });

  it("justo en el límite no se trunca", () => {
    expect(previewExcerpt("a".repeat(30), 30).truncated).toBe(false);
  });
});
