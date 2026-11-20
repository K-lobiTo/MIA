import { describe, expect, it } from "vitest";
import { DELETE_CONSEQUENCES } from "./deleteUtils";

describe("DELETE_CONSEQUENCES", () => {
  it("avisa de lo que se elimina, lo que se conserva y lo de los bots", () => {
    expect(DELETE_CONSEQUENCES).toContain("plantillas");
    expect(DELETE_CONSEQUENCES).toContain("registro de consultas se conserva");
    expect(DELETE_CONSEQUENCES).toContain("No se puede deshacer");
    expect(DELETE_CONSEQUENCES).toContain("bot de WhatsApp");
    expect(DELETE_CONSEQUENCES).not.toContain("—");
  });
});
