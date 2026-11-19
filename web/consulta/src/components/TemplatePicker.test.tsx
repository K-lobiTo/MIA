// @vitest-environment node
import { MantineProvider } from "@mantine/core";
import { renderToString } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import type { Template, TemplatesResponse } from "../api/types";
import { theme } from "../theme";
import { TemplatePicker } from "./TemplatePicker";

const plantilla = (id: string, name: string): Template => ({ id, name, content: "# Resumen", updated_at: "2026-11-18T10:00:00Z" });
const datos = (artifact: Template[], mine: Template[]): TemplatesResponse => ({
  enabled: true,
  limits: { max_chars: 4000, max_per_user: 20, file_max_mb: 1 },
  can_create: true,
  artifact,
  mine,
});

function render(data: TemplatesResponse, selectedId: string | null = null, extra: Partial<React.ComponentProps<typeof TemplatePicker>> = {}): string {
  return renderToString(
    <MantineProvider theme={theme}>
      <TemplatePicker data={data} selectedId={selectedId} onSelect={vi.fn()} {...extra} />
    </MantineProvider>,
  );
}

describe("TemplatePicker", () => {
  it("muestra los dos grupos con sus plantillas", () => {
    const html = render(datos([plantilla("a", "Informe de programa")], [plantilla("m", "Mi ficha")]));
    expect(html).toContain("Del artefacto");
    expect(html).toContain("Mías");
    expect(html).toContain("Informe de programa");
    expect(html).toContain("Mi ficha");
    expect(html.indexOf("Del artefacto")).toBeLessThan(html.indexOf("Mías"));
  });

  it("muestra solo los grupos que tienen plantillas", () => {
    const soloMias = render(datos([], [plantilla("m", "Mi ficha")]));
    expect(soloMias).toContain("Mías");
    expect(soloMias).not.toContain("Del artefacto");
    const soloArtefacto = render(datos([plantilla("a", "Informe")], []));
    expect(soloArtefacto).toContain("Del artefacto");
    expect(soloArtefacto).not.toContain("Mías");
  });

  it("marca la plantilla elegida", () => {
    const html = render(datos([plantilla("a", "Informe")], []), "a");
    expect(html).toMatch(/<option value="a"[^>]*selected/);
  });

  it("sin ninguna plantilla lo dice y da un ejemplo breve", () => {
    const html = render(datos([], []));
    expect(html).toContain("Aún no hay plantillas.");
    expect(html).toContain("Resumen:");
    expect(html).not.toContain("<select");
  });

  it("con sesión ofrece administrar las plantillas personales, también cuando aún no hay ninguna", () => {
    expect(render(datos([plantilla("a", "Informe")], []), null, { onManage: vi.fn() })).toContain("Administrar mis plantillas");
    const vacio = render(datos([], []), null, { onManage: vi.fn() });
    expect(vacio).toContain("Aún no hay plantillas.");
    expect(vacio).toContain("Administrar mis plantillas");
  });

  it("sin sesión invita a iniciarla y no ofrece administrar", () => {
    const html = render({ ...datos([plantilla("a", "Informe")], []), can_create: false }, null, { onManage: vi.fn(), onLogin: vi.fn() });
    expect(html).toContain("Inicia sesión para guardar tus propias plantillas.");
    expect(html).toContain("Iniciar sesión");
    expect(html).not.toContain("Administrar mis plantillas");
  });
});
