import { OTHER } from "./usageUtils";

const SLOTS = 8;

// Memoria de la sesión: cada nombre conserva su color aunque un filtro cambie la cantidad de series
// (el color sigue a la entidad, no a su posición: un filtro no debe repintar a las que quedan).
const remembered = new Map<string, number>();

/** Asigna un color de la paleta categórica (en su orden fijo) a cada serie visible. Un nombre ya visto
 * conserva su paso; los nuevos toman el primero libre. "Otros" va siempre en gris neutro. */
export function assignColors(names: string[], memory: Map<string, number> = remembered): Record<string, string> {
  const used = new Set<number>();
  const result: Record<string, string> = {};
  const pending: string[] = [];
  for (const name of names) {
    if (name === OTHER) {
      result[name] = "var(--series-other)";
      continue;
    }
    const slot = memory.get(name);
    if (slot !== undefined && !used.has(slot)) {
      used.add(slot);
      result[name] = `var(--series-${slot + 1})`;
    } else {
      pending.push(name);
    }
  }
  for (const name of pending) {
    let slot = 0;
    while (used.has(slot) && slot < SLOTS - 1) slot += 1;
    used.add(slot);
    memory.set(name, slot);
    result[name] = `var(--series-${slot + 1})`;
  }
  return result;
}
