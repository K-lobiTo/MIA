import { describe, expect, it } from "vitest";
import { BROWSER_BLOCKED, EXPIRED, INVALID_KEY, describeAccessError, microsoftProblem } from "./errors";

describe("describeAccessError", () => {
  it("cuenta no autorizada nombra el correo y ofrece cerrar sesión", () => {
    const problem = describeAccessError(403, "not_authorized", "alguien@itcr.ac.cr")!;
    expect(problem.kind).toBe("no_autorizada");
    expect(problem.message).toBe(
      "La cuenta alguien@itcr.ac.cr no está autorizada para usar el panel de MIA. Pide acceso a quien administra MIA.",
    );
    expect(problem.action).toBe("cerrar_sesion");
  });

  it("sin correo conocido habla de tu cuenta", () => {
    expect(describeAccessError(403, "not_authorized")!.message).toMatch(/^Tu cuenta no está autorizada/);
  });

  it("sin segundo factor pide completarlo y volver a entrar", () => {
    const problem = describeAccessError(403, "mfa_required")!;
    expect(problem.kind).toBe("sin_mfa");
    expect(problem.message).toContain("verificación en dos pasos");
    expect(problem.action).toBe("iniciar_sesion");
  });

  it("cualquier 401 es sesión vencida", () => {
    for (const code of ["token_expired", "invalid_token", "unauthenticated", undefined]) {
      expect(describeAccessError(401, code)).toEqual(EXPIRED);
    }
    expect(EXPIRED.message).toBe("Tu sesión venció. Inicia sesión de nuevo.");
  });

  it("con la clave de administración un 401 es clave inválida y se vuelve a la pantalla de entrada", () => {
    expect(describeAccessError(401, "unauthenticated", undefined, true)).toEqual(INVALID_KEY);
    expect(INVALID_KEY.message).toBe("La clave de administración no es válida.");
    expect(INVALID_KEY.action).toBe("volver");
    expect(describeAccessError(401, "token_expired", undefined, false)).toEqual(EXPIRED);
  });

  it("la API sin configurar no ofrece ninguna acción", () => {
    const problem = describeAccessError(503, "login_not_configured")!;
    expect(problem.kind).toBe("api_sin_configurar");
    expect(problem.action).toBe("ninguna");
  });

  it("sin claves del directorio se puede reintentar", () => {
    const problem = describeAccessError(503, "identity_unavailable")!;
    expect(problem.kind).toBe("identidad_no_disponible");
    expect(problem.action).toBe("reintentar");
  });

  it("los errores normales de una operación no son problemas de acceso", () => {
    expect(describeAccessError(403, "out_of_scope")).toBeNull();
    expect(describeAccessError(403, "global_only")).toBeNull();
    expect(describeAccessError(404)).toBeNull();
    expect(describeAccessError(409)).toBeNull();
    expect(describeAccessError(422)).toBeNull();
    expect(describeAccessError(0)).toBeNull();
    expect(describeAccessError(503, "otra_cosa")).toBeNull();
  });
});

describe("otros motivos", () => {
  it("el error de Microsoft agrega el detalle si lo hay", () => {
    expect(microsoftProblem().message).toBe("No se completó el inicio de sesión en Microsoft.");
    expect(microsoftProblem("Cancelaste el inicio.").message).toBe(
      "No se completó el inicio de sesión en Microsoft. Cancelaste el inicio.",
    );
  });

  it("el navegador que bloquea el almacenamiento tiene su mensaje", () => {
    expect(BROWSER_BLOCKED.kind).toBe("navegador");
    expect(BROWSER_BLOCKED.message).toContain("bloquea el almacenamiento");
  });
});
