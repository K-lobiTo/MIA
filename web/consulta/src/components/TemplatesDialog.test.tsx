// @vitest-environment node
import { MantineProvider } from "@mantine/core";
import { renderToString } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import type { Template } from "../api/types";
import { theme } from "../theme";
import { MyTemplatesList, TemplateForm } from "./TemplatesDialog";

const plantilla = (id: string, name: string, scope: "all" | "artifact"): Template => ({
  id,
  name,
  content: "# Resumen",
  updated_at: "2026-11-18T10:00:00Z",
  scope,
});

const envolver = (nodo: React.ReactNode) => renderToString(<MantineProvider theme={theme}>{nodo}</MantineProvider>);

function lista(props: Partial<React.ComponentProps<typeof MyTemplatesList>> = {}) {
  return envolver(
    <MyTemplatesList
      templates={[plantilla("a", "Mi informe", "all"), plantilla("b", "Ficha corta", "artifact")]}
      busy={false}
      confirmDeleteId={null}
      removing={false}
      onEdit={vi.fn()}
      onAskDelete={vi.fn()}
      onCancelDelete={vi.fn()}
      onConfirmDelete={vi.fn()}
      {...props}
    />,
  );
}

describe("MyTemplatesList", () => {
  it("muestra las plantillas personales con su alcance", () => {
    const html = lista();
    expect(html).toContain("Mi informe");
    expect(html).toContain("Para todos mis artefactos");
    expect(html).toContain("Ficha corta");
    expect(html).toContain("Solo para este artefacto");
    expect(html.match(/Editar/g)).toHaveLength(2);
  });

  it("pide confirmar antes de eliminar, solo en la fila elegida", () => {
    const html = lista({ confirmDeleteId: "b" });
    expect(html).toContain("¿Eliminar «Ficha corta»?");
    expect(html).not.toContain("¿Eliminar «Mi informe»?");
  });

  it("sin plantillas invita a agregar la primera", () => {
    expect(lista({ templates: [] })).toContain("Todavía no tienes plantillas personales");
  });
});

function formulario(props: Partial<React.ComponentProps<typeof TemplateForm>> = {}) {
  return envolver(
    <TemplateForm
      name="Informe"
      content="# Resumen"
      scope="artifact"
      errors={{ name: null, content: null }}
      maxChars={4000}
      fileMaxMb={1}
      busy={false}
      saving={false}
      extracting={false}
      onName={vi.fn()}
      onContent={vi.fn()}
      onScope={vi.fn()}
      onFile={vi.fn()}
      onCancel={vi.fn()}
      onSubmit={vi.fn()}
      {...props}
    />,
  );
}

describe("TemplateForm", () => {
  it("advierte que no deben ir datos personales y ofrece cargar un archivo sin guardarlo", () => {
    const html = formulario();
    expect(html).toContain("No incluyas datos personales ni información confidencial: la plantilla se guarda tal cual.");
    expect(html).toContain("Cargar archivo (.docx o .txt)");
    expect(html).toContain("El archivo no se guarda");
  });

  it("el alcance por defecto es para este artefacto y ofrece también para todos", () => {
    const html = formulario();
    expect(html).toMatch(/<option value="artifact"[^>]*selected/);
    expect(html).toContain("Para todos mis artefactos");
  });

  it("muestra el contador con el máximo, el tamaño máximo del archivo y el error del contenido", () => {
    const html = formulario({ content: "x".repeat(50), maxChars: 200, fileMaxMb: 2, errors: { name: null, content: "El contenido no puede superar 200 caracteres." } });
    expect(html).toContain("50 de 200 caracteres");
    expect(html).toContain("máximo 2 MB");
    expect(html).toContain("El contenido no puede superar 200 caracteres.");
    expect(html).toMatch(/<button[^>]*disabled[^>]*type="submit"|<button[^>]*type="submit"[^>]*disabled/);
  });
});
