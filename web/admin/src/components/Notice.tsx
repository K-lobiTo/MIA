import { Alert } from "@mantine/core";
import { IconAlertTriangle, IconCircleCheck, IconInfoCircle, IconX } from "@tabler/icons-react";
import type { ReactNode } from "react";

export type Tone = "info" | "ok" | "warn" | "danger";

const ICON = { info: IconInfoCircle, ok: IconCircleCheck, warn: IconAlertTriangle, danger: IconX } as const;
// Los avisos de error y de advertencia se anuncian a los lectores de pantalla de inmediato; los demás, con calma.
const ROLE = { info: "status", ok: "status", warn: "alert", danger: "alert" } as const;

/** Aviso con los colores de la paleta (styles/tokens.css): borde y ícono del color del tono, texto en tinta. */
export function Notice({ tone = "info", title, children }: { tone?: Tone; title?: string; children: ReactNode }) {
  const Icon = ICON[tone];
  const color = tone === "info" ? "var(--accent)" : `var(--${tone})`;
  const soft = tone === "info" ? "var(--accent-soft)" : `var(--${tone}-soft)`;
  return (
    <Alert
      role={ROLE[tone]}
      title={title}
      icon={<Icon size={18} />}
      radius="md"
      styles={{
        root: { background: soft, border: `1px solid ${color}` },
        icon: { color },
        title: { color: "var(--ink)" },
        message: { color: "var(--ink)" },
      }}
    >
      {children}
    </Alert>
  );
}
