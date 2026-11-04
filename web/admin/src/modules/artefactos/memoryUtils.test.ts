import { describe, expect, it } from "vitest";
import { describeMemory, validateTurns } from "./memoryUtils";

describe("validateTurns", () => {
  it.each([
    ["0", 0],
    ["3", 3],
    [" 10 ", 10],
    ["7", 7],
  ])("acepta %s", (texto, valor) => {
    expect(validateTurns(texto)).toEqual({ ok: true, value: valor });
  });

  it.each(["", "  ", "-1", "11", "2.5", "2,5", "tres", "1e1", "+3x"])("rechaza %j con un mensaje claro", (texto) => {
    const resultado = validateTurns(texto);
    expect(resultado.ok).toBe(false);
    if (!resultado.ok) expect(resultado.message).toMatch(/0 y 10/);
  });
});

describe("describeMemory", () => {
  it("dice sin memoria con 0 y las vueltas con singular y plural", () => {
    expect(describeMemory(0)).toBe("Sin memoria");
    expect(describeMemory(1)).toBe("Memoria: 1 vuelta");
    expect(describeMemory(3)).toBe("Memoria: 3 vueltas");
  });
});
