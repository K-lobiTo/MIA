import { describe, expect, it } from "vitest";
import {
  describeConversations,
  describeUserStatus,
  formatDateTime,
  generatePassword,
  normalizeUsername,
  validatePassword,
  validateUsername,
} from "./usuariosUtils";

describe("validateUsername", () => {
  it("acepta de 3 a 40 caracteres de a-z, 0-9, punto, guion y guion bajo, sin distinguir mayúsculas", () => {
    for (const bueno of ["ana", "Ana.Perez", "a_b-c.9", "x".repeat(40), "  ana  "]) {
      expect(validateUsername(bueno), bueno).toBeNull();
    }
  });

  it("rechaza vacío, muy corto o largo, espacios dentro, arrobas y tildes", () => {
    for (const malo of ["", "ab", "x".repeat(41), "ana perez", "ana@itcr.ac.cr", "año"]) {
      expect(validateUsername(malo), malo).toContain("3 a 40 caracteres");
    }
  });

  it("normaliza a minúsculas y recorta", () => {
    expect(normalizeUsername("  Ana.Perez ")).toBe("ana.perez");
  });
});

describe("validatePassword", () => {
  it("vacía vale (el servidor genera una); si se escribe, al menos 10 caracteres y no solo espacios", () => {
    expect(validatePassword("")).toBeNull();
    expect(validatePassword("1234567890")).toBeNull();
    expect(validatePassword("123456789")).toContain("al menos 10");
    expect(validatePassword("            ")).toContain("espacios");
  });
});

describe("generatePassword", () => {
  it("genera 16 caracteres legibles que cumplen el mínimo", () => {
    const clave = generatePassword((n) => Array.from({ length: n }, (_, i) => i * 7));
    expect(clave).toHaveLength(16);
    expect(clave).toMatch(/^[a-zA-Z2-9]+$/);
    expect(clave).not.toMatch(/[lIO01]/);
    expect(validatePassword(clave)).toBeNull();
  });

  it("con el generador del navegador cada llamada da una distinta", () => {
    expect(generatePassword()).not.toBe(generatePassword());
  });
});

describe("textos del usuario", () => {
  it("el estado dice el texto, nunca solo el color", () => {
    expect(describeUserStatus({ active: true })).toEqual({ text: "Activo", tone: "ok" });
    expect(describeUserStatus({ active: false })).toEqual({ text: "Desactivado", tone: "neutral" });
  });

  it("describe las conversaciones en singular y plural", () => {
    expect(describeConversations(0)).toBe("Sin conversaciones guardadas");
    expect(describeConversations(1)).toBe("1 conversación");
    expect(describeConversations(7)).toBe("7 conversaciones");
  });

  it("la fecha sin dato dice Nunca y una inválida también", () => {
    expect(formatDateTime(null)).toBe("Nunca");
    expect(formatDateTime("no es una fecha")).toBe("Nunca");
    expect(formatDateTime("2026-11-04T16:02:00Z")).toContain("2026");
  });
});
