import { Badge } from "@mantine/core";
import type { ReactNode } from "react";

export type BadgeTone = "ok" | "warn" | "danger" | "info" | "neutral";

/** Etiqueta de estado con los colores de la paleta; el texto siempre dice el estado (nunca solo el color). */
export function StatusBadge({ tone = "info", title, children }: { tone?: BadgeTone; title?: string; children: ReactNode }) {
  const style =
    tone === "neutral"
      ? { background: "var(--bg)", color: "var(--muted)", border: "1px solid var(--line)" }
      : {
          background: tone === "info" ? "var(--accent-soft)" : `var(--${tone}-soft)`,
          color: tone === "info" ? "var(--accent)" : `var(--${tone})`,
        };
  return (
    <Badge variant="light" radius="xl" tt="none" fw={600} title={title} style={style} styles={{ root: { overflow: "visible", height: "auto", padding: "3px 10px" }, label: { overflow: "visible", textOverflow: "clip" } }}>
      {children}
    </Badge>
  );
}
