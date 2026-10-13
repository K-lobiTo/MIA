// Textos de los rechazos de acceso: specs/004-acceso-panel-tec/contracts/ui-panel.md.

export type AccessKind =
  | "no_autorizada"
  | "sin_mfa"
  | "vencida"
  | "api_sin_configurar"
  | "identidad_no_disponible"
  | "microsoft"
  | "navegador"
  | "clave_invalida";

export type AccessAction = "cerrar_sesion" | "iniciar_sesion" | "reintentar" | "volver" | "ninguna";

export interface AccessProblem {
  kind: AccessKind;
  message: string;
  action: AccessAction;
}

export const EXPIRED: AccessProblem = {
  kind: "vencida",
  message: "Tu sesión venció. Inicia sesión de nuevo.",
  action: "iniciar_sesion",
};

export const INVALID_KEY: AccessProblem = {
  kind: "clave_invalida",
  message: "La clave de administración no es válida.",
  action: "volver",
};

export const BROWSER_BLOCKED: AccessProblem = {
  kind: "navegador",
  message:
    "Tu navegador bloquea el almacenamiento necesario para iniciar sesión. Revisa que no estés en una ventana privada estricta o que las cookies y el almacenamiento del sitio estén permitidos.",
  action: "reintentar",
};

export function microsoftProblem(detail?: string): AccessProblem {
  const suffix = detail ? ` ${detail}` : "";
  return {
    kind: "microsoft",
    message: `No se completó el inicio de sesión en Microsoft.${suffix}`,
    action: "iniciar_sesion",
  };
}

/** Traduce un error de la API a un problema de acceso (que deja la sesión inutilizable), o a null si
 * es un error normal de la operación (conflicto, fuera de alcance, sin conexión...). */
export function describeAccessError(
  status: number,
  code?: string,
  email?: string,
  byKey = false,
): AccessProblem | null {
  // Con la clave de administración un 401 es una clave incorrecta, no una sesión vencida.
  if (status === 401) return byKey ? INVALID_KEY : EXPIRED;
  if (status === 403 && code === "not_authorized") {
    return {
      kind: "no_autorizada",
      message: `${email ? `La cuenta ${email}` : "Tu cuenta"} no está autorizada para usar el panel de MIA. Pide acceso a quien administra MIA.`,
      action: "cerrar_sesion",
    };
  }
  if (status === 403 && code === "mfa_required") {
    return {
      kind: "sin_mfa",
      message: "El inicio de sesión no incluyó la verificación en dos pasos. Complétala en Microsoft e intenta de nuevo.",
      action: "iniciar_sesion",
    };
  }
  if (status === 503 && code === "login_not_configured") {
    return {
      kind: "api_sin_configurar",
      message: "El inicio de sesión todavía no está disponible en esta instancia de MIA.",
      action: "ninguna",
    };
  }
  if (status === 503 && code === "identity_unavailable") {
    return {
      kind: "identidad_no_disponible",
      message: "No se pudo verificar tu identidad ahora mismo. Intenta de nuevo en unos minutos.",
      action: "reintentar",
    };
  }
  return null;
}
