const STORAGE_KEY = "mia-consulta-menu";

/** Ancho del menú lateral. Con 300 el botón «Nueva conversación» quedaba recortado junto al título. */
export const SIDEBAR_WIDTH = 340;

/** Si el menú lateral está abierto en pantallas anchas. Abierto por defecto; la elección se recuerda en el navegador. */
export function loadSidebarOpen(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) !== "cerrado";
  } catch {
    return true;
  }
}

export function saveSidebarOpen(open: boolean): void {
  try {
    localStorage.setItem(STORAGE_KEY, open ? "abierto" : "cerrado");
  } catch {
    // Sin almacenamiento disponible: la elección no se recuerda.
  }
}
