// @vitest-environment node
import { MantineProvider } from "@mantine/core";
import { renderToString } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import type { DocumentItem } from "../../api/types";
import { theme } from "../../theme";
import { DocumentRow } from "./TreeNode";

const documento: DocumentItem = {
  id: "doc1",
  filename: "horario_matricula.pdf",
  source_type: "pdf",
  status: "done",
  uploaded_at: "2026-10-07T00:00:00Z",
  folder_id: null,
  image_count: 2,
};

function render(document: DocumentItem, onImages?: (document: DocumentItem) => void): string {
  return renderToString(
    <MantineProvider theme={theme}>
      <DocumentRow document={document} onImages={onImages} />
    </MantineProvider>,
  );
}

describe("DocumentRow", () => {
  it("muestra el botón de imágenes con su contador", () => {
    const html = render(documento, vi.fn());
    expect(html).toContain("horario_matricula.pdf");
    expect(html).toContain("Imágenes (2)");
    expect(html).toContain("Imágenes de horario_matricula.pdf");
  });

  it("un documento sin imágenes muestra el contador en cero", () => {
    expect(render({ ...documento, image_count: 0 }, vi.fn())).toContain("Imágenes (0)");
  });

  it("sin acción para abrir las imágenes no muestra el botón", () => {
    expect(render(documento)).not.toContain("Imágenes");
  });
});
