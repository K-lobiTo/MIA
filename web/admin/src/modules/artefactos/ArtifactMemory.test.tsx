// @vitest-environment node
import { MantineProvider } from "@mantine/core";
import { renderToString } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import type { Artifact } from "../../api/types";
import { theme } from "../../theme";
import { ArtifactCard } from "./ArtifactCard";
import { MEMORY_HELP } from "./memoryUtils";

const artefacto: Artifact = {
  id: "a1",
  name: "Consulta Computación",
  description: "",
  key_prefix: "mia_aaaa",
  active: true,
  access: { all_domains: false, unit_ids: [], domain_ids: [] },
  allowed_domain_count: 3,
  modes: ["literal"],
  daily_cap_usd: 0.5,
  reasoning_daily_cap_usd: null,
  context_turns: 3,
  today: { spent_usd: 0, reasoning_spent_usd: 0, cap_reached: false, reasoning_cap_reached: false },
  queries_last_7_days: 0,
  created_at: "2026-11-03T00:00:00Z",
};

function tarjeta(a: Artifact): string {
  return renderToString(
    <MantineProvider theme={theme}>
      <ArtifactCard artifact={a} units={[]} busy={false} onEdit={vi.fn()} onRegenerate={vi.fn()} onToggleActive={vi.fn()} />
    </MantineProvider>,
  );
}

describe("ArtifactCard", () => {
  it("muestra la memoria de conversación", () => {
    expect(tarjeta(artefacto)).toContain("Memoria: 3 vueltas");
    expect(tarjeta({ ...artefacto, context_turns: 0 })).toContain("Sin memoria");
  });
});

describe("texto del formulario", () => {
  it("explica el costo y que 0 es el comportamiento de siempre", () => {
    expect(MEMORY_HELP).toContain("cada consulta lleva más texto y cuesta más");
    expect(MEMORY_HELP).toContain("0 es el comportamiento de siempre");
  });
});
