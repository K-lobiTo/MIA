import type { ReactElement } from "react";
import type { Capabilities } from "../auth/capabilities";
import { ArtefactosPage } from "./artefactos/ArtefactosPage";
import { BotsPage } from "./bots/BotsPage";
import { EquivalenciasPage } from "./equivalencias/EquivalenciasPage";
import { InventarioPage } from "./inventario/InventarioPage";
import { UsoPage } from "./uso/UsoPage";

export interface PanelModule {
  path: string;
  label: string;
  element: ReactElement;
  // Capacidad que la sesión debe tener para ver el módulo en el menú (ver visibleModules.ts).
  requires?: keyof Capabilities;
}

// Agregar un módulo nuevo es sumar una entrada aquí (ADM-3) y un grupo de rutas en la API.
export const MODULES: PanelModule[] = [
  { path: "/inventario", label: "Inventario de información", element: <InventarioPage /> },
  { path: "/artefactos", label: "Artefactos y accesos", element: <ArtefactosPage /> },
  { path: "/uso", label: "Uso", element: <UsoPage /> },
  { path: "/siglas", label: "Siglas y equivalencias", element: <EquivalenciasPage /> },
  { path: "/bots", label: "Bots", element: <BotsPage />, requires: "canManageBots" },
];
