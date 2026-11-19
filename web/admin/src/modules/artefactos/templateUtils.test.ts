import { describe, expect, it } from "vitest";
import { MANAGE_WARNING, describeTemplateCount, templateFormValid, validateTemplateForm } from "./templateUtils";

describe("validateTemplateForm", () => {
  it("acepta un nombre y un contenido válidos", () => {
    const errors = validateTemplateForm("Informe de programa", "# Resumen", 4000);
    expect(errors).toEqual({ name: null, content: null });
    expect(templateFormValid(errors)).toBe(true);
  });

  it("rechaza el nombre vacío, con saltos de línea o de más de 80 caracteres, con los mensajes de la API", () => {
    expect(validateTemplateForm("  ", "x", 4000).name).toBe("El nombre no puede estar vacío.");
    expect(validateTemplateForm("dos\nlíneas", "x", 4000).name).toBe("El nombre no puede tener saltos de línea.");
    expect(validateTemplateForm("a".repeat(81), "x", 4000).name).toBe("El nombre no puede superar 80 caracteres.");
    expect(validateTemplateForm("a".repeat(80), "x", 4000).name).toBeNull();
  });

  it("rechaza el contenido vacío o mayor que el máximo, con el límite en el mensaje", () => {
    expect(validateTemplateForm("a", "   ", 4000).content).toBe("El contenido no puede estar vacío.");
    expect(validateTemplateForm("a", "x".repeat(201), 200).content).toBe("El contenido no puede superar 200 caracteres.");
    expect(validateTemplateForm("a", "x".repeat(200), 200).content).toBeNull();
    expect(templateFormValid(validateTemplateForm("", "", 200))).toBe(false);
  });

  it("la advertencia de datos personales y el texto del botón", () => {
    expect(MANAGE_WARNING).toContain("datos personales");
    expect(describeTemplateCount(0)).toBe("Plantillas");
    expect(describeTemplateCount(3)).toBe("Plantillas (3)");
  });
});
