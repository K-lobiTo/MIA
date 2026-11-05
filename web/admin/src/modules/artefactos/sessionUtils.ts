// "Exigir inicio de sesión" de un artefacto (feature 015): solo responde a personas con usuario de la Consulta.
export const REQUIRE_LOGIN_LABEL = "Exigir inicio de sesión para consultar";
export const REQUIRE_LOGIN_HELP =
  "Si está activo, este artefacto solo responde a personas con usuario. Desactivado, cualquiera con la clave puede consultar (sin guardar conversaciones).";

export function describeSession(requireLogin: boolean): string {
  return requireLogin ? "Exige sesión" : "Sin sesión";
}
