import type { ModeId } from "../api/types";

// Texto fijo para la conversación vacía: orienta qué tipo de pregunta conviene a cada modo. No se envía.
const EXAMPLES: Record<ModeId, string[]> = {
  literal: [
    "¿Qué se acordó en las actas sobre las becas?",
    "¿Cuántas horas extraclase por semana tiene el curso de Cibercrimen?",
  ],
  razonamiento: [
    "¿Cuántos créditos suman los cursos de Sistemas Operativos Avanzados, Análisis de Algoritmos y Diseño de Experimentos?",
    "¿Cuántas horas tiene cada uno de estos dos cursos y cuál tiene más?",
  ],
};

export function examplesFor(mode: ModeId): string[] {
  return EXAMPLES[mode];
}
