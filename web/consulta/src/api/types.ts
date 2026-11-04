// Tipos de los contratos de la API (specs/002-panel-administracion/contracts/api-consulta.md y
// specs/003-consulta-administrativa/contracts/api-consulta-modos.md).

export type ModeId = "literal" | "razonamiento";
export type Rating = "util" | "no_util";

export interface Mode {
  id: ModeId;
  name: string;
  description: string;
  available: boolean;
  reason: string | null;
}

export interface Caps {
  cap_reached: boolean;
  reasoning_cap_reached: boolean;
  global_cap_reached: boolean;
  resets_at: string;
}

export interface Config {
  ingestion_enabled: boolean;
  max_upload_mb: number;
  modes: Mode[];
  // Solo cuando se pidió con la clave de un artefacto.
  // `context_turns`: cuántas vueltas anteriores recuerda el artefacto (0: ninguna; feature 014).
  artifact?: { name: string; active: boolean; context_turns?: number };
  caps?: Caps;
}

export interface Domain {
  id: string;
  unit_id: string | null;
  unit_name: string | null;
  name: string;
  description: string;
}

export interface Source {
  domain: string;
  document: string;
  excerpt: string;
}

/** Una vuelta anterior de la conversación que se envía como memoria (feature 014). */
export interface HistoryTurn {
  question: string;
  answer: string;
  mode: ModeId;
}

export interface QueryResponse {
  id: string;
  answer: string;
  sources: Source[];
  mode: ModeId;
  latency_ms: number;
  no_info: boolean;
}
