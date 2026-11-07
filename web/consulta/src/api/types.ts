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
  artifact?: { name: string; active: boolean; context_turns?: number; require_login?: boolean };
  // Historial de chats (feature 015): si se guardan las conversaciones y por cuántos días.
  chat?: { enabled: boolean; retention_days: number };
  caps?: Caps;
}

export interface Domain {
  id: string;
  unit_id: string | null;
  unit_name: string | null;
  name: string;
  description: string;
  // Etiqueta: su contenido cambia cada periodo y solo trae información vigente (p. ej. Promoción).
  dynamic?: boolean;
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
  // Solo con sesión de usuario (feature 015): la conversación donde quedó y si se pudo guardar.
  conversation_id?: string | null;
  saved?: boolean;
}

// Conversaciones guardadas (feature 015, contracts/conversaciones-api.md).
export interface ConversationSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  turn_count: number;
}

export interface ConversationsResponse {
  retention_days: number;
  conversations: ConversationSummary[];
}

export interface StoredTurn {
  position: number;
  question: string;
  answer: string;
  sources: { domain: string; document: string }[];
  mode: ModeId;
  no_info: boolean;
  created_at: string;
}

export interface StoredConversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  turns: StoredTurn[];
}
