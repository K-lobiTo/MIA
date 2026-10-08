import type { ReactElement } from "react";
import { ArtefactosPage } from "./artefactos/ArtefactosPage";
import { InventarioPage } from "./inventario/InventarioPage";
import { UsoPage } from "./uso/UsoPage";

export interface PanelModule {
  path: string;
  label: string;
  // Sin la clave de administración el módulo aparece deshabilitado en el menú (ADM-1).
  needsAdmin: boolean;
  element: ReactElement;
}

// Agregar un módulo nuevo es sumar una entrada aquí (ADM-3) y un grupo de rutas en la API.
export const MODULES: PanelModule[] = [
  { path: "/inventario", label: "Inventario de información", needsAdmin: false, element: <InventarioPage /> },
  { path: "/artefactos", label: "Artefactos y accesos", needsAdmin: true, element: <ArtefactosPage /> },
  { path: "/uso", label: "Uso", needsAdmin: true, element: <UsoPage /> },
];
