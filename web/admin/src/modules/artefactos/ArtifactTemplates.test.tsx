// @vitest-environment node
import { MantineProvider } from "@mantine/core";
import { renderToString } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import type { Artifact, ArtifactTemplate } from "../../api/types";
import { theme } from "../../theme";
import { ArtifactCard } from "./ArtifactCard";
import { TemplateEditor, TemplatesList } from "./ArtifactTemplatesDialog";
import { MANAGE_WARNING } from "./templateUtils";

const artefacto: Artifact = {
  id: "a1",
  name: "Consulta Computación",
  description: "",
  key_prefix: "mia_aaaa",
  active: true,
  access: { all_domains: false, unit_ids: [], domain_ids: [] },
  allowed_domain_count: 3,
  modes: ["literal", "razonamiento", "plantilla"],
  daily_cap_usd: 0.5,
  reasoning_daily_cap_usd: null,
  context_turns: 0,
  require_login: false,
  custom_prompt: "",
  template_count: 3,
  today: { spent_usd: 0, reasoning_spent_usd: 0, cap_reached: false, reasoning_cap_reached: false },
  queries_last_7_days: 0,
  created_at: "2026-11-18T00:00:00Z",
};

const envolver = (nodo: React.ReactNode) => renderToString(<MantineProvider theme={theme}>{nodo}</MantineProvider>);

const tarjeta = (a: Artifact) =>
  envolver(
    <ArtifactCard artifact={a} units={[]} busy={false} onEdit={vi.fn()} onRegenerate={vi.fn()} onToggleActive={vi.fn()} onTemplates={vi.fn()} onDelete={vi.fn()} />,
  );

describe("ArtifactCard y las plantillas", () => {
  it("con el modo plantilla muestra el botón con la cantidad", () => {
    expect(tarjeta(artefacto)).toContain("Plantillas (3)");
    expect(tarjeta({ ...artefacto, template_count: 0 })).toContain(">Plantillas<");
  });

  it("sin el modo plantilla no ofrece el botón", () => {
    expect(tarjeta({ ...artefacto, modes: ["literal"] })).not.toContain("Plantillas");
  });

  it("nombra los tres modos del artefacto", () => {
    expect(tarjeta(artefacto)).toContain("Literal, Con razonamiento y Plantilla");
  });
});

const plantilla = (id: string, name: string, content = "# Resumen"): ArtifactTemplate => ({
  id,
  name,
  content,
  updated_at: "2026-11-18T10:00:00Z",
});

function lista(props: Partial<React.ComponentProps<typeof TemplatesList>> = {}) {
  return envolver(
    <TemplatesList
      templates={[plantilla("t1", "Informe de programa", "x".repeat(120)), plantilla("t2", "Ficha corta")]}
      busy={false}
      confirmDeleteId={null}
      removing={false}
      loading={false}
      onEdit={vi.fn()}
      onAskDelete={vi.fn()}
      onCancelDelete={vi.fn()}
      onConfirmDelete={vi.fn()}
      {...props}
    />,
  );
}

describe("TemplatesList", () => {
  it("muestra los nombres con su tamaño y las acciones", () => {
    const html = lista();
    expect(html).toContain("Informe de programa");
    expect(html).toContain("Ficha corta");
    expect(html).toContain("120 caracteres");
    expect(html.match(/Editar/g)).toHaveLength(2);
    expect(html.match(/Eliminar/g)).toHaveLength(2);
  });

  it("pide confirmar antes de eliminar, solo en la fila elegida", () => {
    const html = lista({ confirmDeleteId: "t2" });
    expect(html).toContain("¿Eliminar «Ficha corta»?");
    expect(html).not.toContain("¿Eliminar «Informe de programa»?");
  });

  it("sin plantillas lo dice, y mientras carga no", () => {
    expect(lista({ templates: [] })).toContain("todavía no tiene plantillas");
    expect(lista({ templates: [], loading: true })).not.toContain("todavía no tiene plantillas");
  });
});

function editor(props: Partial<React.ComponentProps<typeof TemplateEditor>> = {}) {
  return envolver(
    <TemplateEditor
      name="Informe"
      content="# Resumen"
      errors={{ name: null, content: null }}
      maxChars={4000}
      fileMaxMb={1}
      busy={false}
      saving={false}
      extracting={false}
      onName={vi.fn()}
      onContent={vi.fn()}
      onFile={vi.fn()}
      onCancel={vi.fn()}
      onSubmit={vi.fn()}
      {...props}
    />,
  );
}

describe("TemplateEditor", () => {
  it("advierte que no deben ir datos personales y ofrece cargar un archivo", () => {
    const html = editor();
    expect(html).toContain(MANAGE_WARNING);
    expect(html).toContain("Cargar archivo (.docx o .txt)");
    expect(html).toContain("El archivo no se guarda");
  });

  it("muestra el contador con el máximo del contenido y el tamaño máximo del archivo", () => {
    const html = editor({ content: "x".repeat(50), maxChars: 200, fileMaxMb: 2 });
    expect(html).toContain("50 de 200 caracteres");
    expect(html).toContain("máximo 2 MB");
  });

  it("deshabilita Guardar si el formulario no es válido y muestra el error del campo", () => {
    const html = editor({ errors: { name: null, content: "El contenido no puede superar 200 caracteres." }, content: "x".repeat(300) });
    expect(html).toContain("El contenido no puede superar 200 caracteres.");
    expect(html).toMatch(/<button[^>]*disabled[^>]*type="submit"|<button[^>]*type="submit"[^>]*disabled/);
  });
});

describe("ArtifactCard y eliminar", () => {
  it("ofrece el botón Eliminar", () => {
    expect(tarjeta(artefacto)).toContain("Eliminar");
    expect(tarjeta({ ...artefacto, modes: ["literal"] })).toContain("Eliminar");
  });
});
