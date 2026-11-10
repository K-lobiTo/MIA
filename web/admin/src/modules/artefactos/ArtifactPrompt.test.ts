import { describe, expect, it } from "vitest";
import { MAX_PROMPT_CHARS, describePrompt, validatePrompt } from "./promptUtils";

describe("prompt propio del artefacto", () => {
  it("acepta hasta el máximo y rechaza más", () => {
    expect(validatePrompt("a".repeat(MAX_PROMPT_CHARS))).toBeNull();
    expect(validatePrompt("a".repeat(MAX_PROMPT_CHARS + 1))).toContain("Máximo");
  });

  it("describe el vacío o en blanco como las instrucciones de siempre", () => {
    expect(describePrompt("")).toBe("Las de siempre");
    expect(describePrompt("  \n ")).toBe("Las de siempre");
    expect(describePrompt("  Hola ")).toBe("Propias (4 caracteres)");
  });
});
