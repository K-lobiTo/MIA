import type { Me } from "../api/types";

export interface Capabilities {
  canCreateUnit: boolean;
  canSeeBalance: boolean;
  canUseAllDomains: boolean;
  canEditEquivalences: boolean;
  showGlobalCaps: boolean;
}

/** Qué puede hacer la sesión según su alcance (GET /me). Solo decide qué mostrar: la API es la que
 * hace cumplir los permisos. */
export function capabilities(me: Pick<Me, "is_global"> | null | undefined): Capabilities {
  const global = Boolean(me?.is_global);
  return {
    canCreateUnit: global,
    canSeeBalance: global,
    canUseAllDomains: global,
    canEditEquivalences: global,
    showGlobalCaps: global,
  };
}

/** "Global" o los nombres de las unidades, para mostrar en la barra lateral. */
export function scopeLabel(me: Me): string {
  if (me.is_global) return "Global";
  return me.units.map((unit) => unit.name).join(", ") || "Sin programas";
}
