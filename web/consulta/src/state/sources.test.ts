import { describe, expect, it } from "vitest";
import { uniqueDocuments } from "./sources";

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
