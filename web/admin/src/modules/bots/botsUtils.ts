import type { Artifact, Bot, UnitNode } from "../../api/types";
import type { BadgeTone } from "../../components/StatusBadge";

/** Valida el número de Kapso (su `phone_number_id`): de 1 a 64 caracteres y sin espacios. Devuelve el motivo si no vale. */
export function validateNumberId(text: string): string | null {
  const value = text.trim();
  if (value === "") return "Escribe el identificador del número de Kapso (su phone_number_id).";
  if (/\s/.test(value)) return "El identificador no debe tener espacios.";
  if (value.length > 64) return "El identificador tiene como máximo 64 caracteres.";
  return null;
}

/** Estado del bot en una etiqueta: el texto siempre lo dice, nunca solo el color. */
export function describeBotStatus(bot: Pick<Bot, "active" | "available">): { text: string; tone: BadgeTone } {
  if (!bot.active) return { text: "Desactivado", tone: "neutral" };
  if (!bot.available) return { text: "No responde", tone: "danger" };
  return { text: "Activo", tone: "ok" };
}

/** Porcentaje del tope mensual ya usado, entre 0 y 100, para la barra. */
export function percentOfCap(total: number, cap: number): number {
  if (cap <= 0) return 100;
  return Math.max(0, Math.min(100, (total / cap) * 100));
}

/** Estado de la barra de mensajes: normal, cerca del tope (desde 80 %) o alcanzado. */
export function usageLevel(total: number, cap: number): "ok" | "warn" | "full" {
  if (total >= cap) return "full";
  return percentOfCap(total, cap) >= 80 ? "warn" : "ok";
}

/** "2026-10" como "octubre de 2026". */
export function monthLabel(month: string): string {
  const match = /^(\d{4})-(\d{2})$/.exec(month);
  if (!match) return month;
  const date = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, 1));
  return new Intl.DateTimeFormat("es", { month: "long", year: "numeric", timeZone: "UTC" }).format(date);
}

/** Los dominios que vería un bot con este artefacto, como "Programa / Dominio" y ordenados, para la advertencia que se
 * muestra al asignarlo. Se calcula del acceso del artefacto y del inventario. */
export function domainsOfArtifact(artifact: Pick<Artifact, "access">, units: UnitNode[]): string[] {
  const labels = new Set<string>();
  const { all_domains, unit_ids, domain_ids } = artifact.access;
  for (const unit of units) {
    for (const domain of unit.domains) {
      if (all_domains || unit_ids.includes(unit.id) || domain_ids.includes(domain.id)) {
        labels.add(`${unit.name} / ${domain.name}`);
      }
    }
  }
  return [...labels].sort((a, b) => a.localeCompare(b, "es"));
}

/** Advertencia de acceso público que se confirma al asignar un artefacto a un bot (BOT-7). */
export const PUBLIC_ACCESS_WARNING =
  "Este bot responde a cualquiera que escriba al número. Los dominios del artefacto deben ser información que se pueda decir a cualquiera.";
