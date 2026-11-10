// @vitest-environment node
import { MantineProvider } from "@mantine/core";
import { renderToString } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import type { Artifact } from "../../api/types";
import { theme } from "../../theme";
import { ArtifactCard } from "./ArtifactCard";
import { REQUIRE_LOGIN_HELP, REQUIRE_LOGIN_LABEL, describeSession } from "./sessionUtils";

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
  context_turns: 0,
  require_login: false,
  custom_prompt: "",
  today: { spent_usd: 0, reasoning_spent_usd: 0, cap_reached: false, reasoning_cap_reached: false },
  queries_last_7_days: 0,
  created_at: "2026-11-04T00:00:00Z",
};

function tarjeta(a: Artifact): string {
  return renderToString(
    <MantineProvider theme={theme}>
      <ArtifactCard artifact={a} units={[]} busy={false} onEdit={vi.fn()} onRegenerate={vi.fn()} onToggleActive={vi.fn()} />
    </MantineProvider>,
  );
}

describe("ArtifactCard: inicio de sesión", () => {
  it("dice si el artefacto exige sesión o no", () => {
    expect(tarjeta(artefacto)).toContain("Sin sesión");
    expect(tarjeta({ ...artefacto, require_login: true })).toContain("Exige sesión");
  });
});

describe("texto del formulario", () => {
  it("explica qué pasa activo y desactivado", () => {
    expect(REQUIRE_LOGIN_LABEL).toBe("Exigir inicio de sesión para consultar");
    expect(REQUIRE_LOGIN_HELP).toContain("solo responde a personas con usuario");
    expect(REQUIRE_LOGIN_HELP).toContain("sin guardar conversaciones");
    expect(describeSession(true)).toBe("Exige sesión");
    expect(describeSession(false)).toBe("Sin sesión");
  });
});
