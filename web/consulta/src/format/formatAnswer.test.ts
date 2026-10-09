import { describe, expect, it } from "vitest";
import { formatAnswer } from "./formatAnswer";

const plain = (text: string) => ({ text, bold: false });
const bold = (text: string) => ({ text, bold: true });

describe("formatAnswer", () => {
  it("separa párrafos por líneas vacías", () => {
    expect(formatAnswer("Primero.\n\nSegundo.")).toEqual([
      { kind: "paragraph", segments: [plain("Primero.")] },
      { kind: "paragraph", segments: [plain("Segundo.")] },
    ]);
  });

  it("reconoce negritas dentro de una línea", () => {
    expect(formatAnswer("Suman **12 créditos** en total")).toEqual([
      { kind: "paragraph", segments: [plain("Suman "), bold("12 créditos"), plain(" en total")] },
    ]);
  });

  it("convierte líneas con * o - en una lista con viñetas", () => {
    expect(formatAnswer("* uno\n- dos **b**")).toEqual([
      { kind: "bullets", items: [[plain("uno")], [plain("dos "), bold("b")]] },
    ]);
  });

  it("convierte líneas con 1. o 1) en una lista numerada", () => {
    expect(formatAnswer("1. uno\n2) dos")).toEqual([
      { kind: "numbered", items: [[plain("uno")], [plain("dos")]] },
    ]);
  });

  it("cambiar de tipo de lista cierra la anterior", () => {
    const blocks = formatAnswer("- a\n1. b");
    expect(blocks.map((b) => b.kind)).toEqual(["bullets", "numbered"]);
  });

  it("una línea con # se vuelve un párrafo en negrita sin los #", () => {
    expect(formatAnswer("## Lo que dicen los documentos")).toEqual([
      { kind: "paragraph", segments: [bold("Lo que dicen los documentos")] },
    ]);
  });

  it("el HTML del modelo queda como texto literal", () => {
    expect(formatAnswer('<script>alert("x")</script>')).toEqual([
      { kind: "paragraph", segments: [plain('<script>alert("x")</script>')] },
    ]);
  });

  it("un texto vacío no produce bloques", () => {
    expect(formatAnswer("  \n\n ")).toEqual([]);
  });

  it("una negrita sin cerrar queda como texto", () => {
    expect(formatAnswer("Dato **sin cerrar")).toEqual([{ kind: "paragraph", segments: [plain("Dato **sin cerrar")] }]);
  });
});
