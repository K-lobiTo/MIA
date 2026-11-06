import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { loadSidebarOpen, saveSidebarOpen } from "./sidebar";

// Vitest corre en Node, sin localStorage: se simula uno en memoria.
function fakeStorage() {
  const data = new Map<string, string>();
  return {
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => void data.set(key, value),
    removeItem: (key: string) => void data.delete(key),
  };
}

describe("loadSidebarOpen y saveSidebarOpen", () => {
  beforeEach(() => vi.stubGlobal("localStorage", fakeStorage()));
  afterEach(() => vi.unstubAllGlobals());

  it("sin nada guardado el menú está abierto", () => {
    expect(loadSidebarOpen()).toBe(true);
  });

  it("recuerda que se cerró y que se volvió a abrir", () => {
    saveSidebarOpen(false);
    expect(loadSidebarOpen()).toBe(false);
    saveSidebarOpen(true);
    expect(loadSidebarOpen()).toBe(true);
  });

  it("sin almacenamiento disponible queda abierto y no lanza", () => {
    vi.stubGlobal("localStorage", {
      getItem: () => {
        throw new Error("bloqueado");
      },
      setItem: () => {
        throw new Error("bloqueado");
      },
    });
    expect(loadSidebarOpen()).toBe(true);
    expect(() => saveSidebarOpen(false)).not.toThrow();
  });
});
