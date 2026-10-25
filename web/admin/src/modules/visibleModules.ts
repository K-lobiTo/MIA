import type { Capabilities } from "../auth/capabilities";

export interface ModuleLike {
  path: string;
  // Capacidad que la sesión debe tener para ver el módulo en el menú; sin ella, lo ven todas las personas que administran.
  requires?: keyof Capabilities;
}

/** Los módulos que la sesión ve en el menú. Solo decide qué mostrar: la API es la que hace cumplir los permisos. */
export function visibleModules<T extends ModuleLike>(modules: T[], caps: Capabilities): T[] {
  return modules.filter((module) => !module.requires || caps[module.requires]);
}
