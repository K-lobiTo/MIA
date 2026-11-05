import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { clearSession, getSession, loadSession, saveSession } from "./session";

function almacen(inicial: Record<string, string> = {}) {
  const datos = new Map(Object.entries(inicial));
  return {
    getItem: (k: string) => datos.get(k) ?? null,
    setItem: (k: string, v: string) => void datos.set(k, v),
    removeItem: (k: string) => void datos.delete(k),
    datos,
  };
}

describe("sesión en el navegador", () => {
  beforeEach(() => {
    vi.stubGlobal("localStorage", almacen());
    clearSession();
  });
  afterEach(() => vi.unstubAllGlobals());

  it("guarda el token y el nombre, y se leen de nuevo", () => {
    saveSession({ token: "mias_abc", username: "ana" });

    expect(getSession()).toEqual({ token: "mias_abc", username: "ana" });
    expect(loadSession()).toEqual({ token: "mias_abc", username: "ana" });
  });

  it("cerrar la sesión la borra de la memoria y del almacenamiento", () => {
    saveSession({ token: "mias_abc", username: "ana" });

    clearSession();

    expect(getSession()).toBeNull();
    expect(loadSession()).toBeNull();
  });

  it("un valor guardado dañado o incompleto se ignora", () => {
    for (const malo of ["no es json", "{}", '{"token":"x"}', '{"token":1,"username":"a"}', "null"]) {
      vi.stubGlobal("localStorage", almacen({ "mia-consulta-session": malo }));
      expect(loadSession(), malo).toBeNull();
    }
  });

  it("si el almacenamiento falla la sesión vive en memoria y nada se rompe", () => {
    const roto = {
      getItem: () => {
        throw new Error("bloqueado");
      },
      setItem: () => {
        throw new Error("bloqueado");
      },
      removeItem: () => {
        throw new Error("bloqueado");
      },
    };
    vi.stubGlobal("localStorage", roto);

    expect(loadSession()).toBeNull();
    expect(() => saveSession({ token: "mias_abc", username: "ana" })).not.toThrow();
    expect(getSession()).toEqual({ token: "mias_abc", username: "ana" });
    expect(() => clearSession()).not.toThrow();
    expect(getSession()).toBeNull();
  });
});
