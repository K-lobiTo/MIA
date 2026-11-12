// Tipos de las respuestas de la API, según specs/002-panel-administracion/contracts/.

export type DocumentStatus = "pending" | "processing" | "done" | "error";

export interface DocumentItem {
  id: string;
  filename: string;
  source_type: string;
  status: DocumentStatus;
  uploaded_at: string;
  folder_id: string | null;
  // Imágenes asociadas al documento (feature 011).
  image_count: number;
}

export interface FolderNode {
  id: string;
  name: string;
  parent_id: string | null;
  document_count: number;
  folders: FolderNode[];
  documents: DocumentItem[];
}

export interface DomainNode {
  id: string;
  name: string;
  description: string;
  // Etiqueta: el contenido cambia cada periodo (p. ej. Promoción). Funcionalmente es un dominio como los demás.
  dynamic?: boolean;
  document_count: number;
  folders: FolderNode[];
  documents: DocumentItem[];
}

export interface UnitNode {
  id: string;
  name: string;
  description: string;
  document_count: number;
  domains: DomainNode[];
}

export interface Inventory {
  ingestion_enabled: boolean;
  max_upload_mb: number;
  units: UnitNode[];
  unassigned_domains: DomainNode[];
}

export interface Unit {
  id: string;
  name: string;
  description: string;
}

export interface VisibleTo {
  now: string[];
  needs_enabling: string[];
}

export interface DomainCreated {
  id: string;
  unit_id: string;
  name: string;
  description: string;
  dynamic?: boolean;
  visible_to: VisibleTo;
}

export type ModeId = "literal" | "razonamiento";

export interface ArtifactAccess {
  all_domains: boolean;
  unit_ids: string[];
  domain_ids: string[];
}

export interface Artifact {
  id: string;
  name: string;
  description: string;
  key_prefix: string;
  active: boolean;
  access: ArtifactAccess;
  allowed_domain_count: number;
  modes: ModeId[];
  daily_cap_usd: number;
  reasoning_daily_cap_usd: number | null;
  // Vueltas que recuerda el artefacto (feature 014); 0: sin memoria.
  context_turns: number;
  // Solo responde a personas con sesión de usuario de la Consulta (feature 015).
  require_login: boolean;
  // Instrucciones propias, anexas a las del modo de respuesta; vacío: ninguna.
  custom_prompt: string;
  today: {
    spent_usd: number;
    reasoning_spent_usd: number;
    cap_reached: boolean;
    reasoning_cap_reached: boolean;
  };
  queries_last_7_days: number;
  created_at: string;
}

// Solo al crear: la clave completa se muestra una única vez.
export interface ArtifactCreated extends Artifact {
  key: string;
}

export interface ModeInfo {
  id: ModeId;
  name: string;
  available: boolean;
  avg_cost_usd_7d: number | null;
}

export interface ArtifactsResponse {
  artifacts: Artifact[];
  // Nulo para quien tiene alcance de unidad: el gasto de toda la API no es suyo.
  global: {
    daily_cap_usd: number;
    spent_today_usd: number;
    sum_of_artifact_caps_usd: number;
    caps_exceed_global: boolean;
  } | null;
  modes: ModeInfo[];
}

// Imágenes asociadas a documentos (feature 011, contracts/imagenes-api.md).
export interface ImageItem {
  id: string;
  public_id: string;
  // Ruta relativa `/media/{public_id}`: se completa con la dirección de la API.
  url: string;
  content_type: "image/png" | "image/jpeg";
  size_bytes: number;
  caption: string;
  position: number;
}

export interface ImagesResponse {
  images: ImageItem[];
  max_image_mb: number;
}

// Bots de WhatsApp (feature 011, contracts/bots-api.md).
export interface BotArtifactRef {
  id: string;
  name: string;
  active: boolean;
}

export interface BotUsage {
  received: number;
  sent: number;
  total: number;
  cap_reached: boolean;
}

export interface Bot {
  id: string;
  name: string;
  kapso_number_id: string;
  active: boolean;
  artifact: BotArtifactRef | null;
  // Etiquetas "Programa / Dominio" de lo que el bot ve hoy (los dominios del artefacto asignado).
  domains: string[];
  available: boolean;
  unavailable_reason: string | null;
  usage: BotUsage;
  // Vueltas de memoria propias del bot (null: la predeterminada) y las que rigen (feature 014).
  context_turns: number | null;
  context_turns_effective: number;
  created_at: string;
}

export interface BotsResponse {
  monthly_cap: number;
  service_configured: boolean;
  month: string;
  bots: Bot[];
}

export interface ConfigResponse {
  ingestion_enabled: boolean;
  max_upload_mb: number;
  modes: { id: ModeId; name: string; description: string; available: boolean; reason: string | null }[];
}

export interface KpiValue {
  value: number;
  previous: number | null;
  change_pct?: number | null;
  change_pts?: number | null;
}

export interface UsageResponse {
  period: { from: string; to: string; bucket: "hour" | "day" | "month" };
  kpis: {
    spend_usd: KpiValue;
    queries: KpiValue;
    tokens: KpiValue & { input: number; output: number; reasoning: number };
    avg_cost_usd: KpiValue;
    latency_ms: { p50: number | null; p95: number | null; previous_p50: number | null; change_pct: number | null };
    no_info_pct: KpiValue;
    error_pct: KpiValue;
    useful_pct: KpiValue & { rated: number };
  };
  series: { bucket: string; groups: Record<string, { spend_usd: number; queries: number; tokens: number }> }[];
  by_artifact: {
    id: string;
    name: string;
    today_spent_usd: number;
    daily_cap_usd: number;
    spend_usd: number;
    queries: number;
    avg_latency_ms: number | null;
  }[];
  by_model: { model: string; queries: number; tokens: number; spend_usd: number; avg_latency_ms: number | null }[];
}

export type Outcome = "answered" | "no_info" | "error" | "rejected_cap" | "rejected_permission";

export interface QueryLogItem {
  id: string;
  created_at: string;
  artifact: string | null;
  mode: ModeId;
  model: string | null;
  tokens: number | null;
  cost_usd: number;
  cost_estimated: boolean;
  latency_ms: number | null;
  outcome: Outcome;
  reject_reason: string | null;
  rating: "util" | "no_util" | null;
}

export interface QueryLogPage {
  total: number;
  page: number;
  page_size: number;
  items: QueryLogItem[];
}

export interface QueryLogDetail extends QueryLogItem {
  question: string;
  domains: string[];
  sources: { domain: string; document: string }[];
  rating_comment: string | null;
}

export interface BalanceResponse {
  available: boolean;
  reason?: string;
  remaining_usd?: number;
  source?: "key_limit" | "account";
  key_limit_remaining_usd?: number | null;
  account_remaining_usd?: number | null;
  days_left?: number | null;
  avg_daily_spend_usd_7d?: number;
  warning?: boolean;
}

export interface Equivalence {
  id: string;
  sigla: string;
  form: string;
  created_by: string;
  created_at: string;
  updated_by: string | null;
  updated_at: string | null;
}

export interface EquivalencesResponse {
  equivalences: Equivalence[];
}

export interface EquivalenceInput {
  sigla: string;
  form: string;
}

export interface Me {
  email: string | null;
  is_global: boolean;
  units: { id: string; name: string }[];
  source: string;
}

// Eliminación de documentos (feature 012).
export type DeleteStatus = "deleted" | "not_found" | "out_of_scope" | "busy" | "error";

export interface DeleteResultItem {
  document_id: string;
  filename?: string;
  status: DeleteStatus;
  detail?: string;
}

export interface BulkDeleteResponse {
  deleted: number;
  failed: number;
  results: DeleteResultItem[];
}

// Usuarios de la Consulta (feature 015, contracts/usuarios-admin-api.md). La administración solo ve cantidad y fecha de las
// conversaciones, nunca su texto.
export interface ConsultaUser {
  id: string;
  username: string;
  unit: { id: string; name: string } | null;
  active: boolean;
  created_at: string;
  last_login_at: string | null;
  conversation_count: number;
  last_activity_at: string | null;
}

// La contraseña solo viene al crear: es la única vez que se puede ver.
export interface ConsultaUserCreated extends ConsultaUser {
  password: string;
}

export interface ConsultaUsersResponse {
  users: ConsultaUser[];
}

// Contactos de WhatsApp (feature 017, contracts/contactos-admin-api.md). Datos personales: solo el alcance global los ve.
export type ContactStatus = "pendiente" | "invitada" | "entrego" | "declino";

export interface Contact {
  id: string;
  phone: string;
  bot: { id: string; name: string };
  name: string | null;
  email: string | null;
  status: ContactStatus;
  created_at: string;
  last_seen_at: string;
  updated_at: string;
}

export interface ContactsResponse {
  total: number;
  page: number;
  page_size: number;
  items: Contact[];
  // Conteo por estado sin el filtro de estado (pero con los demás filtros).
  summary: Record<ContactStatus, number>;
}
