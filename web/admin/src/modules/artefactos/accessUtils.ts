import type { ArtifactAccess, ModeId, UnitNode } from "../../api/types";

/** Acceso de un artefacto en lenguaje claro (ART-1): "Todos los dominios", programas completos y
 * dominios elegidos uno a uno. */
export function describeAccess(access: ArtifactAccess, units: UnitNode[]): string {
  if (access.all_domains) return "Todos los dominios (incluye los de programas futuros)";
  const parts: string[] = [];
  for (const unitId of access.unit_ids) {
    const unit = units.find((u) => u.id === unitId);
    parts.push(`${unit ? unit.name : "(programa eliminado)"} (programa completo)`);
  }
  for (const domainId of access.domain_ids) {
    const unit = units.find((u) => u.domains.some((d) => d.id === domainId));
    const domain = unit?.domains.find((d) => d.id === domainId);
    parts.push(domain ? `${unit!.name} / ${domain.name}` : "(dominio eliminado)");
  }
  return parts.length > 0 ? parts.join("; ") : "Sin acceso";
}

export const MODE_LABEL: Record<ModeId, string> = {
  literal: "Literal",
  razonamiento: "Con razonamiento",
  plantilla: "Plantilla",
};

export function describeModes(modes: ModeId[]): string {
  if (modes.length === 0) return "Ninguno";
  const labels = modes.map((m) => MODE_LABEL[m]);
  return labels.length === 1 ? labels[0] : `${labels.slice(0, -1).join(", ")} y ${labels[labels.length - 1]}`;
}

/** Costo medio de un modo en los últimos 7 días. El modo plantilla usa el modelo del razonamiento: sin consultas propias
 * se estima con las del razonamiento. */
export function avgCostOf(mode: ModeId, modes: { id: ModeId; avg_cost_usd_7d: number | null }[]): number | null {
  const own = modes.find((m) => m.id === mode)?.avg_cost_usd_7d ?? null;
  if (own !== null || mode !== "plantilla") return own;
  return modes.find((m) => m.id === "razonamiento")?.avg_cost_usd_7d ?? null;
}

/** Costo aproximado por consulta de un modo, para decidir qué modos permitir (ART-4). */
export function describeCost(avgCostUsd: number | null | undefined): string {
  if (avgCostUsd === null || avgCostUsd === undefined) return "sin consultas recientes para estimarlo";
  const digits = avgCostUsd >= 0.1 ? 2 : avgCostUsd >= 0.01 ? 3 : 4;
  return `unos ${avgCostUsd.toFixed(digits)} USD por consulta`;
}

/** Quita de la selección de dominios los que ya cubre una unidad completa elegida. */
export function pruneCoveredDomains(unitIds: string[], domainIds: string[], units: UnitNode[]): string[] {
  const covered = new Set(units.filter((u) => unitIds.includes(u.id)).flatMap((u) => u.domains.map((d) => d.id)));
  return domainIds.filter((id) => !covered.has(id));
}
