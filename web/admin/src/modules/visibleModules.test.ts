import { describe, expect, it } from "vitest";
import type { Me } from "../api/types";
import { capabilities } from "../auth/capabilities";
import { visibleModules } from "./visibleModules";

const modulos = [
  { path: "/inventario" },
  { path: "/bots", requires: "canManageBots" as const },
  { path: "/contactos", requires: "canManageContacts" as const },
  { path: "/uso" },
];

const global: Me = { email: "g@itcr.ac.cr", is_global: true, source: "entra", units: [] };
const unidad: Me = { email: "a@itcr.ac.cr", is_global: false, source: "entra", units: [{ id: "1", name: "Computación" }] };

describe("visibleModules", () => {
  it("el alcance global ve todos los módulos, incluidos Bots y Contactos de WhatsApp", () => {
    expect(visibleModules(modulos, capabilities(global)).map((m) => m.path)).toEqual(["/inventario", "/bots", "/contactos", "/uso"]);
  });

  it("el alcance de programa no ve los módulos Bots ni Contactos de WhatsApp", () => {
    expect(visibleModules(modulos, capabilities(unidad)).map((m) => m.path)).toEqual(["/inventario", "/uso"]);
  });

  it("sin perfil solo se ven los módulos que no exigen nada", () => {
    expect(visibleModules(modulos, capabilities(null)).map((m) => m.path)).toEqual(["/inventario", "/uso"]);
  });
});
