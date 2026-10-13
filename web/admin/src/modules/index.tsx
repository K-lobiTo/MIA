import type { ReactElement } from "react";
import { ArtefactosPage } from "./artefactos/ArtefactosPage";
import { InventarioPage } from "./inventario/InventarioPage";
import { UsoPage } from "./uso/UsoPage";

export interface PanelModule {
  path: string;
  label: string;
  element: ReactElement;
}

// Agregar un módulo nuevo es sumar una entrada aquí (ADM-3) y un grupo de rutas en la API.
export const MODULES: PanelModule[] = [
  { path: "/inventario", label: "Inventario de información", element: <InventarioPage /> },
  { path: "/artefactos", label: "Artefactos y accesos", element: <ArtefactosPage /> },
  { path: "/uso", label: "Uso", element: <UsoPage /> },
];
