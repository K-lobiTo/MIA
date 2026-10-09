import type { Config, Mode, ModeId } from "../api/types";

export interface Availability {
  /** Modos que se muestran: los que el artefacto tiene permitidos (la API ya no envía los demás). */
  modes: Mode[];
  /** El selector solo aparece si hay más de un modo permitido (CON-2). */
  showSelector: boolean;
  /** Modo con el que se pregunta; nulo si ninguno está disponible. */
  effective: ModeId | null;
  /** El modo guardado ya no estaba disponible y se eligió otro: se avisa a la persona. */
  changed: boolean;
  /** Motivo por el que no se puede enviar ninguna pregunta (tope alcanzado, sin modos disponibles), o nulo. */
  sendBlocked: string | null;
}

/** Decide qué modos mostrar y con cuál preguntar, a partir de `/config` y del modo guardado (CON-2, CON-3). */
export function resolveAvailability(config: Config, savedMode: string | null): Availability {
  const modes = config.modes;
  const available = modes.filter((m) => m.available);
  const saved = available.find((m) => m.id === savedMode);
  const effective = saved?.id ?? available[0]?.id ?? null;
  const capReached = Boolean(config.caps?.cap_reached || config.caps?.global_cap_reached);
  let sendBlocked: string | null = null;
  if (capReached || effective === null) {
    sendBlocked =
      modes.find((m) => m.reason)?.reason ??
      (capReached
        ? "Se alcanzó el tope diario de gasto. Se reinicia a la medianoche."
        : "No hay un modo de respuesta disponible.");
  }
  return {
    modes,
    showSelector: modes.length > 1,
    effective,
    changed: savedMode !== null && effective !== null && effective !== savedMode,
    sendBlocked,
  };
}

const STORAGE_KEY = "mia-consulta-modo";

// Almacenamiento: puede fallar o estar vacío (ventana privada, datos bloqueados).
export function loadMode(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

export function saveMode(mode: ModeId): void {
  try {
    localStorage.setItem(STORAGE_KEY, mode);
  } catch {
    // Sin almacenamiento disponible: el modo no se recuerda.
  }
}
