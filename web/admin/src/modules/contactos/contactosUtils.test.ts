import { describe, expect, it } from "vitest";
import { toQuery } from "../../api/contacts";
import {
  EMPTY_FORM,
  STATUS_LABEL,
  bulkText,
  bulkTitle,
  formatDate,
  formatPhone,
  hasFilters,
  pageCount,
  toFilters,
} from "./contactosUtils";

describe("contactosUtils", () => {
  it("cada estado tiene un texto y un tono de la paleta, sin grises", () => {
    expect(Object.keys(STATUS_LABEL).sort()).toEqual(["declino", "entrego", "invitada", "pendiente"]);
    expect(STATUS_LABEL.entrego).toEqual({ text: "Dejó sus datos", tone: "ok" });
    for (const label of Object.values(STATUS_LABEL)) {
      expect(label.text.length).toBeGreaterThan(3);
      expect(["ok", "warn", "danger", "info", "neutral"]).toContain(label.tone);
    }
  });

  it("sin elegir nada no hay filtros; con alguna elección se convierten a los de la API", () => {
    expect(hasFilters(EMPTY_FORM)).toBe(false);
    expect(toFilters(EMPTY_FORM)).toEqual({ status: [] });
    const form = { botId: "b1", statuses: ["entrego" as const, "invitada" as const], email: "con" as const };
    expect(hasFilters(form)).toBe(true);
    expect(toFilters(form)).toEqual({ bot_id: "b1", status: ["entrego", "invitada"], has_email: true });
    expect(toFilters({ ...EMPTY_FORM, email: "sin" })).toEqual({ status: [], has_email: false });
  });

  it("los filtros viajan como parámetros: el estado se repite y los vacíos no van", () => {
    expect(toQuery({ status: [] })).toBe("");
    const query = toQuery({ bot_id: "b1", status: ["entrego", "declino"], has_email: false }, { page: "2" });
    expect(new URLSearchParams(query).getAll("status")).toEqual(["entrego", "declino"]);
    expect(new URLSearchParams(query).get("bot_id")).toBe("b1");
    expect(new URLSearchParams(query).get("has_email")).toBe("false");
    expect(new URLSearchParams(query).get("page")).toBe("2");
  });

  it("la ventana de confirmación del borrado masivo dice cuántos se borran y que no se puede deshacer", () => {
    expect(bulkTitle(1)).toBe("Borrar 1 contacto");
    expect(bulkTitle(12)).toBe("Borrar 12 contactos");
    const text = bulkText(12, true);
    expect(text).toContain("12 contactos");
    expect(text).toContain("cumplen los filtros");
    expect(text).toContain("no se puede deshacer");
    expect(bulkText(3, false)).toContain("todos los contactos");
  });

  it("el teléfono de Costa Rica se agrupa y los demás se dejan como llegaron", () => {
    expect(formatPhone("+50688887777")).toBe("+506 8888-7777");
    expect(formatPhone("+16315551181")).toBe("+16315551181");
  });

  it("la fecha se muestra legible y una ilegible se deja tal cual", () => {
    expect(formatDate("2026-11-12T15:04:05Z")).toMatch(/2026|26/);
    expect(formatDate("no es fecha")).toBe("no es fecha");
  });

  it("siempre hay al menos una página", () => {
    expect(pageCount(0, 50)).toBe(1);
    expect(pageCount(50, 50)).toBe(1);
    expect(pageCount(51, 50)).toBe(2);
  });
});
