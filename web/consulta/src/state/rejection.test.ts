import { describe, expect, it } from "vitest";
import { INVALID_QUESTION_MESSAGE, rejectionOf } from "./rejection";

describe("rejectionOf", () => {
  it("un 422 devuelve la pregunta al campo con el mensaje de la interfaz", () => {
    expect(rejectionOf({ status: 422, message: "String should have at most 2000 characters" }, "mi pregunta")).toEqual({
      restore: "mi pregunta",
      message: INVALID_QUESTION_MESSAGE,
    });
  });

  it("los demás errores no son un rechazo de contenido", () => {
    for (const status of [0, -1, 401, 403, 429, 502]) {
      expect(rejectionOf({ status, message: "x" }, "p")).toBeNull();
    }
  });
});
