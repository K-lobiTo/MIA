// Tipos de las respuestas de la API, según specs/002-panel-administracion/contracts/.

export type DocumentStatus = "pending" | "processing" | "done" | "error";

export interface DocumentItem {
  id: string;
  filename: string;
  source_type: string;
  status: DocumentStatus;
  uploaded_at: string;
  folder_id: string | null;
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
  today: {
    spent_usd: number;
    reasoning_spent_usd: number;
    cap_reached: boolean;
    reasoning_cap_reached: boolean;
  };
  queries_last_7_days: number;
  created_at: string;
  key?: string;
}

export interface ModeInfo {
  id: ModeId;
  name: string;
  available: boolean;
  avg_cost_usd_7d: number | null;
}

export interface ArtifactsResponse {
  artifacts: Artifact[];
  global: {
    daily_cap_usd: number;
    spent_today_usd: number;
    sum_of_artifact_caps_usd: number;
    caps_exceed_global: boolean;
  };
  modes: ModeInfo[];
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
  period: { from: string; to: string; bucket: "hour" | "day" };
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
