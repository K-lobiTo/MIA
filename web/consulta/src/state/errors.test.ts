import { describe, expect, it } from "vitest";
import { describeError } from "./errors";

const error = (status: number, message: string) => ({ status, message });

describe("describeError", () => {
  it("sin conexión: mensaje claro y reintentar", () => {
    expect(describeError(error(0, "x"), "literal")).toEqual({
      message: "No se pudo conectar con MIA. Revisa tu conexión.",
      canRetry: true,
      offerLiteral: false,
    });
  });

  it("tiempo agotado: reintentar y, en razonamiento, reintentar en literal", () => {
    expect(describeError(error(-1, "x"), "literal")).toMatchObject({
      message: "MIA tardó demasiado en responder.",
      canRetry: true,
      offerLiteral: false,
    });
    expect(describeError(error(-1, "x"), "razonamiento")).toMatchObject({ canRetry: true, offerLiteral: true });
  });

  it("502: modelo no disponible; en razonamiento ofrece el literal", () => {
    expect(describeError(error(502, "x"), "razonamiento")).toEqual({
      message: "El modelo de lenguaje no está disponible en este momento.",
      canRetry: true,
      offerLiteral: true,
    });
    expect(describeError(error(502, "x"), "literal").offerLiteral).toBe(false);
  });

  it("429: muestra el motivo de la API, no se reintenta igual y en razonamiento ofrece el literal", () => {
    const detail = "Este artefacto alcanzó su tope diario del modo con razonamiento (1.00 USD). Se reinicia a la medianoche.";
    expect(describeError(error(429, detail), "razonamiento")).toEqual({
      message: detail,
      canRetry: false,
      offerLiteral: true,
    });
  });

  it("429: si el literal tampoco está disponible no lo ofrece", () => {
    expect(describeError(error(429, "tope"), "razonamiento", false).offerLiteral).toBe(false);
  });

  it("403 por artefacto desactivado: explica y manda a quien administra MIA, sin reintentar", () => {
    expect(describeError(error(403, "Este artefacto está desactivado."), "literal")).toEqual({
      message: "Este artefacto está desactivado. Comunícate con quien administra MIA.",
      canRetry: false,
      offerLiteral: false,
    });
  });

  it("403 por permisos: muestra el motivo y permite reintentar con los dominios actualizados", () => {
    expect(describeError(error(403, "Este artefacto no tiene acceso a los dominios: d9."), "literal")).toEqual({
      message: "Este artefacto no tiene acceso a los dominios: d9.",
      canRetry: true,
      offerLiteral: false,
    });
  });

  it("otro error: muestra el estado y el mensaje y permite reintentar", () => {
    expect(describeError(error(500, "falló"), "literal")).toMatchObject({
      message: "Error 500: falló",
      canRetry: true,
    });
  });
});
