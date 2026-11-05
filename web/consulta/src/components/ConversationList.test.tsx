// @vitest-environment node
import { MantineProvider } from "@mantine/core";
import { renderToString } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import type { ConversationSummary } from "../api/types";
import { theme } from "../theme";
import { ConversationList } from "./ConversationList";

const conversaciones: ConversationSummary[] = [
  { id: "c2", title: "Costo de la maestría", created_at: "2026-11-04T10:00:00Z", updated_at: "2026-11-04T12:00:00Z", turn_count: 3 },
  { id: "c1", title: "Requisitos de ingreso", created_at: "2026-11-01T10:00:00Z", updated_at: "2026-11-01T12:00:00Z", turn_count: 1 },
];

function render(props: Partial<React.ComponentProps<typeof ConversationList>> = {}): string {
  return renderToString(
    <MantineProvider theme={theme}>
      <ConversationList conversations={conversaciones} activeId={null} onOpen={vi.fn()} onNew={vi.fn()} {...props} />
    </MantineProvider>,
  );
}

describe("ConversationList", () => {
  it("lista los títulos en el orden recibido y ofrece una conversación nueva", () => {
    const html = render();
    expect(html.indexOf("Costo de la maestría")).toBeLessThan(html.indexOf("Requisitos de ingreso"));
    expect(html).toContain("Nueva conversación");
  });

  it("marca la conversación abierta", () => {
    const html = render({ activeId: "c1" });
    expect(html).toContain('aria-current="true"');
    expect(html.match(/aria-current/g)).toHaveLength(1);
  });

  it("sin conversaciones lo dice, y mientras carga también", () => {
    expect(render({ conversations: [] })).toContain("Todavía no tienes conversaciones guardadas");
    expect(render({ conversations: [], loading: true })).toContain("Cargando conversaciones");
  });
});

describe("ConversationList: borrar y retención", () => {
  it("ofrece borrar cada conversación y borrarlas todas", () => {
    const html = render({ onDelete: vi.fn(), onDeleteAll: vi.fn() });
    expect(html).toContain("Borrar conversación: Costo de la maestría");
    expect(html).toContain("Borrar conversación: Requisitos de ingreso");
    expect(html).toContain("Borrar todas");
  });

  it("sin conversaciones no ofrece borrar todas", () => {
    expect(render({ conversations: [], onDelete: vi.fn(), onDeleteAll: vi.fn() })).not.toContain("Borrar todas");
  });

  it("avisa cuántos días se guardan las conversaciones y que se pueden borrar", () => {
    const html = render({ retentionDays: 90 });
    expect(html).toContain("Tus conversaciones se guardan 90 días sin actividad");
    expect(html).toContain("puedes borrarlas cuando quieras");
  });

  it("sin retención informada no muestra el aviso", () => {
    expect(render()).not.toContain("Tus conversaciones se guardan");
  });
});
