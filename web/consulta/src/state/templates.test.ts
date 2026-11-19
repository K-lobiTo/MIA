import { afterEach, describe, expect, it, vi } from "vitest";
import type { Template, TemplatesResponse } from "../api/types";
import {
  MANAGE_WARNING,
  PICK_TEMPLATE,
  SCOPE_LABEL,
  allTemplates,
  loadTemplateId,
  resolveTemplateSelection,
  restoreTemplate,
  saveTemplateId,
  templateFormValid,
  validateTemplateForm,
} from "./templates";

const plantilla = (id: string, scope?: "all" | "artifact"): Template => ({
  id,
  name: `Plantilla ${id}`,
  content: "# Resumen",
  updated_at: "2026-11-18T10:00:00Z",
  scope,
});
const datos = (artifact: Template[], mine: Template[] = []): TemplatesResponse => ({
  enabled: true,
  limits: { max_chars: 4000, max_per_user: 20, file_max_mb: 1 },
  can_create: mine.length > 0,
  artifact,
  mine,
});

describe("resolveTemplateSelection", () => {
  it("usa la plantilla guardada si todavía está en la lista, del artefacto o personal", () => {
    const data = datos([plantilla("a")], [plantilla("m", "all")]);
    expect(resolveTemplateSelection("plantilla", data, "a")).toMatchObject({ template: { id: "a" }, blocked: null });
    expect(resolveTemplateSelection("plantilla", data, "m")).toMatchObject({ template: { id: "m" }, blocked: null });
  });

  it("descarta la guardada si ya no está y pide elegir una cuando el modo es plantilla", () => {
    const data = datos([plantilla("a")]);
    expect(resolveTemplateSelection("plantilla", data, "borrada")).toEqual({ template: null, blocked: PICK_TEMPLATE });
    expect(resolveTemplateSelection("plantilla", data, null).blocked).toBe("Elige una plantilla.");
  });

  it("con otro modo no bloquea aunque no haya plantilla", () => {
    expect(resolveTemplateSelection("literal", datos([]), null)).toEqual({ template: null, blocked: null });
    expect(resolveTemplateSelection("razonamiento", undefined, null).blocked).toBeNull();
  });

  it("allTemplates junta las del artefacto y las personales", () => {
    expect(allTemplates(datos([plantilla("a")], [plantilla("m")])).map((t) => t.id)).toEqual(["a", "m"]);
    expect(allTemplates(undefined)).toEqual([]);
  });
});

describe("plantilla elegida por artefacto", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("se recuerda por clave de artefacto y se puede olvidar", () => {
    const store: Record<string, string> = {};
    vi.stubGlobal("localStorage", {
      getItem: (k: string) => store[k] ?? null,
      setItem: (k: string, v: string) => void (store[k] = v),
      removeItem: (k: string) => void delete store[k],
    });
    saveTemplateId("clave-1", "t1");
    saveTemplateId("clave-2", "t2");
    expect(loadTemplateId("clave-1")).toBe("t1");
    expect(loadTemplateId("clave-2")).toBe("t2");
    saveTemplateId("clave-1", null);
    expect(loadTemplateId("clave-1")).toBeNull();
  });

  it("sin almacenamiento disponible no falla", () => {
    vi.stubGlobal("localStorage", {
      getItem: () => {
        throw new Error("bloqueado");
      },
      setItem: () => {
        throw new Error("bloqueado");
      },
      removeItem: () => {
        throw new Error("bloqueado");
      },
    });
    expect(loadTemplateId("k")).toBeNull();
    expect(() => saveTemplateId("k", "t")).not.toThrow();
  });
});

describe("validateTemplateForm", () => {
  it("acepta un formulario válido y rechaza nombre y contenido con los mensajes de la API", () => {
    expect(validateTemplateForm("Informe", "# Resumen", 4000)).toEqual({ name: null, content: null });
    expect(validateTemplateForm(" ", "x", 4000).name).toBe("El nombre no puede estar vacío.");
    expect(validateTemplateForm("a\nb", "x", 4000).name).toBe("El nombre no puede tener saltos de línea.");
    expect(validateTemplateForm("a".repeat(81), "x", 4000).name).toBe("El nombre no puede superar 80 caracteres.");
    expect(validateTemplateForm("a", "  ", 4000).content).toBe("El contenido no puede estar vacío.");
    expect(validateTemplateForm("a", "x".repeat(201), 200).content).toBe("El contenido no puede superar 200 caracteres.");
    expect(templateFormValid(validateTemplateForm("a", "x", 200))).toBe(true);
    expect(templateFormValid(validateTemplateForm("", "x", 200))).toBe(false);
  });

  it("la advertencia y los textos de alcance", () => {
    expect(MANAGE_WARNING).toBe("No incluyas datos personales ni información confidencial: la plantilla se guarda tal cual.");
    expect(SCOPE_LABEL.artifact).toBe("Solo para este artefacto");
    expect(SCOPE_LABEL.all).toBe("Para todos mis artefactos");
  });
});

describe("restoreTemplate (retomar una conversación guardada)", () => {
  const data = datos([plantilla("a")], [plantilla("m", "all")]);

  it("deja seleccionada la plantilla de la conversación si sigue en la lista, del artefacto o personal", () => {
    expect(restoreTemplate({ id: "a", name: "Plantilla a" }, data)).toEqual({ selectedId: "a", notice: null });
    expect(restoreTemplate({ id: "m", name: "Plantilla m" }, data)).toEqual({ selectedId: "m", notice: null });
  });

  it("si ya no está disponible pide elegir otra y nombra la anterior", () => {
    expect(restoreTemplate({ id: "borrada", name: "Informe viejo" }, data)).toEqual({
      selectedId: null,
      notice: 'La plantilla "Informe viejo" ya no está disponible. Elige otra.',
    });
    expect(restoreTemplate({ id: "borrada", name: "" }, data).notice).toBe("La plantilla de esta conversación ya no está disponible. Elige otra.");
  });

  it("una conversación sin plantilla no cambia nada", () => {
    expect(restoreTemplate(null, data)).toEqual({ selectedId: null, notice: null });
  });
});
