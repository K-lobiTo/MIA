// @vitest-environment node
import { MantineProvider } from "@mantine/core";
import { renderToString } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { DeletionCheck } from "../../api/structure";
import { theme } from "../../theme";
import { EliminarEstructuraContenido, describirElemento } from "./EliminarEstructuraDialog";

const render = (nodo: React.ReactNode) => renderToString(<MantineProvider theme={theme}>{nodo}</MantineProvider>);

const base: DeletionCheck = { name: "Admisión", can_delete: true, blockers: [], affects: [] };

describe("EliminarEstructuraContenido", () => {
  it("con impedimentos dice cuántos, cuáles y qué hacer, y no ofrece nada como definitivo", () => {
    const html = render(
      <EliminarEstructuraContenido
        tipo="unit"
        check={{
          ...base,
          name: "Computación",
          can_delete: false,
          blockers: [{ kind: "consulta_users", count: 2, names: ["ana", "beto"], hint: "Cámbialos de programa." }],
        }}
      />,
    );
    expect(html).toContain("Computación");
    expect(html).toContain("2 usuarios de la Consulta: ana, beto");
    expect(html).toContain("Cámbialos de programa.");
    expect(html).not.toContain("No se puede deshacer");
  });

  it("sin impedimentos nombra lo que se elimina, a quién afecta y que no se puede deshacer", () => {
    const html = render(
      <EliminarEstructuraContenido
        tipo="domain"
        check={{ ...base, affects: [{ kind: "bots", count: 1, names: ["Bot admisión"], hint: "Responden a personas externas." }] }}
      />,
    );
    expect(html).toContain("Admisión");
    expect(html).toContain("1 bot de WhatsApp: Bot admisión");
    expect(html).toContain("No se puede deshacer");
  });
});

describe("describirElemento", () => {
  it("cuenta documentos sin nombres, resume los que no caben y avisa de los que no se pueden nombrar", () => {
    expect(describirElemento({ kind: "documents", count: 1, names: [], hint: "" })).toBe("1 documento");
    expect(describirElemento({ kind: "domains", count: 12, names: ["a", "b"], hint: "" })).toBe("12 dominios: a, b y 10 más");
    expect(describirElemento({ kind: "artifacts", count: 2, names: [], hint: "" })).toBe("2 artefactos (fuera de lo que administras)");
  });
});
