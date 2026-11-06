// @vitest-environment node
import { AppShell, MantineProvider } from "@mantine/core";
import { renderToString } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import type { ConversationSummary, Domain } from "../api/types";
import { SIDEBAR_WIDTH } from "../state/sidebar";
import { theme } from "../theme";
import { Sidebar } from "./Sidebar";

const dominios: Domain[] = [
  { id: "d1", unit_id: "u1", unit_name: "Computación", name: "Currículum", description: "Planes de estudio" },
  { id: "d2", unit_id: "u1", unit_name: "Computación", name: "Admisión", description: "Requisitos" },
];

const conversaciones: ConversationSummary[] = [
  { id: "c1", title: "Costo de la maestría", created_at: "2026-11-04T10:00:00Z", updated_at: "2026-11-04T12:00:00Z", turn_count: 3 },
];

function render(props: Partial<React.ComponentProps<typeof Sidebar>> = {}): string {
  return renderToString(
    <MantineProvider theme={theme}>
      <AppShell navbar={{ width: SIDEBAR_WIDTH, breakpoint: "sm" }}>
        <Sidebar
          domains={dominios}
          selected={["d1"]}
          onSelect={vi.fn()}
          history={null}
          {...props}
        />
      </AppShell>
    </MantineProvider>,
  );
}

const historia = {
  conversations: conversaciones,
  activeId: null,
  loading: false,
  retentionDays: 90,
  onOpen: vi.fn(),
  onNew: vi.fn(),
  onDelete: vi.fn(),
  onDeleteAll: vi.fn(),
};

describe("Sidebar", () => {
  it("con sesión muestra las conversaciones arriba y los dominios en su propia tarjeta debajo", () => {
    const html = render({ history: historia });
    expect(html).toContain("Conversaciones");
    expect(html).toContain("Costo de la maestría");
    expect(html).toContain("Dominios");
    expect(html.indexOf("Costo de la maestría")).toBeLessThan(html.indexOf("Dominios a consultar"));
    expect(html).toContain("sidebar-domains");
  });

  it("sin sesión y con el guardado activo invita a iniciar sesión en lugar de listar conversaciones", () => {
    const html = render({ onLogin: vi.fn() });
    expect(html).toContain("Guarda tus conversaciones");
    expect(html).toContain("Iniciar sesión");
    expect(html).not.toContain("Nueva conversación");
    expect(html).toContain("Dominios");
  });

  it("sin sesión y sin guardado no muestra ni lista ni invitación", () => {
    const html = render();
    expect(html).not.toContain("Guarda tus conversaciones");
    expect(html).not.toContain("Conversaciones guardadas");
    expect(html).not.toContain("Nueva conversación");
    expect(html).toContain("Dominios");
  });

  it("con sesión pero el guardado apagado avisa que lo que se pregunte no se guarda", () => {
    const html = render({ savingOff: true });
    expect(html).toContain("El guardado de conversaciones está desactivado");
  });

  it("el selector de apariencia va en el menú solo para pantallas angostas", () => {
    expect(render()).toContain("Modo claro");
  });
});
