import { describe, expect, it } from "vitest";
import { fixedKeyFrom } from "./fixedKey";

describe("fixedKeyFrom", () => {
  it("sin configuración no hay clave fija", () => {
    expect(fixedKeyFrom(undefined)).toBe("");
    expect(fixedKeyFrom({})).toBe("");
    expect(fixedKeyFrom({ artifactKey: "" })).toBe("");
  });

  it("devuelve la clave configurada sin espacios alrededor", () => {
    expect(fixedKeyFrom({ artifactKey: "  mia_abc123 \n" })).toBe("mia_abc123");
  });

  it("un valor que no es texto se ignora", () => {
    expect(fixedKeyFrom({ artifactKey: 42 as unknown as string })).toBe("");
  });
});
