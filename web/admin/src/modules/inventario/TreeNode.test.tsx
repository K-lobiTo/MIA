// @vitest-environment node
import { MantineProvider } from "@mantine/core";
import { renderToString } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import type { DocumentItem } from "../../api/types";
import { theme } from "../../theme";
import { DocumentRow, SeleccionContext, type Seleccion } from "./TreeNode";

const documento: DocumentItem = {
  id: "doc1",
  filename: "horario_matricula.pdf",
  source_type: "pdf",
  status: "done",
  uploaded_at: "2026-10-07T00:00:00Z",
  folder_id: null,
  image_count: 2,
};

function render(
  document: DocumentItem,
  onImages?: (document: DocumentItem) => void,
  onDelete?: (document: DocumentItem) => void,
  seleccion?: Seleccion,
): string {
  const fila = <DocumentRow document={document} onImages={onImages} onDelete={onDelete} />;
  return renderToString(
    <MantineProvider theme={theme}>
      {seleccion ? <SeleccionContext.Provider value={seleccion}>{fila}</SeleccionContext.Provider> : fila}
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

  it("muestra el botón Eliminar con su nombre accesible, y no lo muestra sin la acción", () => {
    const html = render(documento, vi.fn(), vi.fn());
    expect(html).toContain("Eliminar horario_matricula.pdf");
    expect(render(documento, vi.fn())).not.toContain("Eliminar horario_matricula.pdf");
  });

  it("la casilla de selección solo aparece en el modo de selección y refleja si está marcado", () => {
    const base: Seleccion = { activa: false, seleccionados: new Set(), alternar: vi.fn(), alternarGrupo: vi.fn() };
    expect(render(documento, undefined, undefined, base)).not.toContain("Seleccionar horario_matricula.pdf");

    const activa = render(documento, undefined, undefined, { ...base, activa: true });
    expect(activa).toContain("Seleccionar horario_matricula.pdf");
    expect(activa).not.toContain("checked");

    const marcado = render(documento, undefined, undefined, { ...base, activa: true, seleccionados: new Set(["doc1"]) });
    expect(marcado).toContain("checked");
  });
});
