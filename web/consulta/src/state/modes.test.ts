import { afterEach, describe, expect, it, vi } from "vitest";
import type { Caps, Config, Mode } from "../api/types";
import { loadMode, resolveAvailability, saveMode } from "./modes";

const literal: Mode = { id: "literal", name: "Literal", description: "", available: true, reason: null };
const razonamiento: Mode = { id: "razonamiento", name: "Con razonamiento", description: "", available: true, reason: null };
const config = (...modes: Mode[]): Config => ({ ingestion_enabled: true, max_upload_mb: 25, modes });
const caps = (parcial: Partial<Caps>): Caps => ({
  cap_reached: false,
  reasoning_cap_reached: false,
  global_cap_reached: false,
  resets_at: "2026-10-10T06:00:00Z",
  ...parcial,
});

describe("resolveAvailability", () => {
  it("con dos modos permitidos muestra el selector y usa el guardado", () => {
    const result = resolveAvailability(config(literal, razonamiento), "razonamiento");
    expect(result).toMatchObject({ showSelector: true, effective: "razonamiento", changed: false });
    expect(result.modes.map((m) => m.id)).toEqual(["literal", "razonamiento"]);
  });

  it("con un solo modo permitido no muestra el selector y lo usa", () => {
    const result = resolveAvailability(config(literal), "razonamiento");
    expect(result.showSelector).toBe(false);
    expect(result.effective).toBe("literal");
    expect(result.changed).toBe(true);
  });

  it("la primera vez, sin modo guardado, usa el primero disponible sin avisar", () => {
    expect(resolveAvailability(config(literal, razonamiento), null)).toMatchObject({
      effective: "literal",
      changed: false,
    });
  });

  it("si el modo guardado no está disponible usa el primero disponible y avisa del cambio", () => {
    const sinRazonamiento = { ...razonamiento, available: false, reason: "Sin modelo." };
    expect(resolveAvailability(config(literal, sinRazonamiento), "razonamiento")).toMatchObject({
      effective: "literal",
      changed: true,
    });
  });

  it("un modo guardado desconocido se reemplaza por el primero disponible", () => {
    expect(resolveAvailability(config(literal), "inventado")).toMatchObject({ effective: "literal", changed: true });
  });

  it("si ningún modo está disponible no hay modo efectivo", () => {
    const apagado = { ...literal, available: false, reason: "Tope alcanzado." };
    expect(resolveAvailability(config(apagado), "literal")).toMatchObject({ effective: null, changed: false });
  });

  it("un modo no disponible se sigue mostrando, deshabilitado, con su motivo", () => {
    const apagado = { ...razonamiento, available: false, reason: "Tope alcanzado." };
    const result = resolveAvailability(config(literal, apagado), null);
    expect(result.modes[1]).toMatchObject({ available: false, reason: "Tope alcanzado." });
  });
});

describe("resolveAvailability: envío bloqueado", () => {
  const apagado = (reason: string) => ({ ...literal, available: false, reason });

  it("sin topes alcanzados el envío no está bloqueado", () => {
    expect(resolveAvailability({ ...config(literal, razonamiento), caps: caps({}) }, null).sendBlocked).toBeNull();
  });

  it("si el tope total del artefacto se alcanzó, bloquea con el motivo que da la API", () => {
    const motivo = "Este artefacto alcanzó su tope diario de gasto. Se reinicia a la medianoche.";
    const resultado = resolveAvailability(
      { ...config(apagado(motivo), { ...razonamiento, available: false, reason: motivo }), caps: caps({ cap_reached: true }) },
      null,
    );
    expect(resultado.sendBlocked).toBe(motivo);
    expect(resultado.effective).toBeNull();
  });

  it("si el tope de toda la API se alcanzó, bloquea aunque los modos no traigan motivo", () => {
    const resultado = resolveAvailability(
      { ...config({ ...literal, available: false, reason: null }), caps: caps({ global_cap_reached: true }) },
      null,
    );
    expect(resultado.sendBlocked).toContain("tope diario de gasto");
    expect(resultado.sendBlocked).toContain("medianoche");
  });

  it("el tope de razonamiento solo deshabilita ese modo: el envío sigue abierto en literal", () => {
    const tope = { ...razonamiento, available: false, reason: "Tope de razonamiento alcanzado." };
    const resultado = resolveAvailability(
      { ...config(literal, tope), caps: caps({ reasoning_cap_reached: true }) },
      "razonamiento",
    );
    expect(resultado.sendBlocked).toBeNull();
    expect(resultado.effective).toBe("literal");
  });

  it("sin ningún modo disponible por otra causa, bloquea con el motivo del modo", () => {
    expect(resolveAvailability(config(apagado("Sin modelo configurado.")), null).sendBlocked).toBe(
      "Sin modelo configurado.",
    );
  });

  it("sin modos ni motivo, bloquea con un mensaje general", () => {
    expect(resolveAvailability(config({ ...literal, available: false, reason: null }), null).sendBlocked).toBe(
      "No hay un modo de respuesta disponible.",
    );
  });
});

describe("loadMode y saveMode", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("guardan y leen el modo", () => {
    const data = new Map<string, string>();
    vi.stubGlobal("localStorage", {
      getItem: (k: string) => data.get(k) ?? null,
      setItem: (k: string, v: string) => void data.set(k, v),
    });
    expect(loadMode()).toBeNull();
    saveMode("razonamiento");
    expect(loadMode()).toBe("razonamiento");
  });

  it("sin almacenamiento no fallan", () => {
    vi.stubGlobal("localStorage", {
      getItem: () => {
        throw new Error("bloqueado");
      },
      setItem: () => {
        throw new Error("bloqueado");
      },
    });
    expect(loadMode()).toBeNull();
    expect(() => saveMode("literal")).not.toThrow();
  });
});
