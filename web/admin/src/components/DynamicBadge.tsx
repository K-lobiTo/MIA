import { StatusBadge } from "./StatusBadge";

export const DYNAMIC_HINT =
  "Dominio dinámico: su contenido cambia cada periodo y solo debe tener información vigente (por ejemplo, Promoción). " +
  "Funciona igual que los demás; es solo una etiqueta.";

/** Etiqueta de los dominios dinámicos (se distinguen de los persistentes, que no llevan etiqueta). */
export function DynamicBadge() {
  return (
    <StatusBadge tone="warn" title={DYNAMIC_HINT}>
      Dinámico
    </StatusBadge>
  );
}
