// @vitest-environment node
import { MantineProvider } from "@mantine/core";
import { renderToString } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import type { DocumentItem, DomainNode } from "../../api/types";
import { theme } from "../../theme";
import { DocumentRow, DomainBranch, SeleccionContext, type Seleccion } from "./TreeNode";

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

  it("muestra la nota de estado de un documento en error y de uno listo con aviso, y nada si no hay nota", () => {
    const nota = "No se pudo leer el libro: el archivo está dañado o protegido con contraseña.";
    const enError = render({ ...documento, source_type: "xlsx", status: "error", status_note: nota });
    expect(enError).toContain(nota);
    expect(enError).toContain("XLSX");

    const recorte = 'El libro se recortó en la fila 5000 de la hoja "Matrícula" por superar el tope de 5000 filas.';
    expect(render({ ...documento, status: "done", status_note: recorte })).toContain("El libro se recortó");

    expect(render(documento)).not.toContain("doc-note");
    expect(render({ ...documento, status_note: null })).not.toContain("doc-note");
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

describe("DomainBranch", () => {
  const dominio = (dynamic?: boolean): DomainNode => ({
    id: "d1",
    name: "Promoción",
    description: "",
    dynamic,
    document_count: 0,
    folders: [],
    documents: [],
  });
  const render = (domain: DomainNode) =>
    renderToString(
      <MantineProvider theme={theme}>
        <DomainBranch domain={domain} forceOpen={false} />
      </MantineProvider>,
    );

  it("etiqueta como dinámico a un dominio dinámico", () => {
    expect(render(dominio(true))).toContain("Dinámico");
  });

  it("no etiqueta a un dominio persistente", () => {
    expect(render(dominio(false))).not.toContain("Dinámico");
    expect(render(dominio(undefined))).not.toContain("Dinámico");
  });
});

describe("documento web (feature 022)", () => {
  const web: DocumentItem = {
    ...documento,
    id: "web1",
    filename: "Maestría de Ejemplo",
    source_type: "web",
    source_url: "https://www.ejemplo.test/programa",
    image_count: 0,
  };

  it("muestra el tipo WEB, la dirección como enlace seguro y la fecha de lectura", () => {
    const html = render(web);
    expect(html).toContain("WEB");
    expect(html).toContain('href="https://www.ejemplo.test/programa"');
    expect(html).toContain('rel="noopener noreferrer"');
    expect(html).toContain('target="_blank"');
    expect(html).toContain("2026");
  });

  it("no hace enlace de una dirección que no es http ni https", () => {
    const html = render({ ...web, source_url: "javascript:alert(1)" });
    expect(html).not.toContain("javascript:alert(1)");
  });

  it("un documento que no es web no muestra dirección", () => {
    expect(render(documento)).not.toContain("Página:");
  });
});

describe("Ver texto de un documento web (feature 022)", () => {
  const web: DocumentItem = { ...documento, id: "web1", filename: "Maestría de Ejemplo", source_type: "web", image_count: 0 };
  const fila = (doc: DocumentItem, onViewText?: (d: DocumentItem) => void) =>
    renderToString(
      <MantineProvider theme={theme}>
        <DocumentRow document={doc} onViewText={onViewText} />
      </MantineProvider>,
    );

  it("un documento web muestra el botón Ver texto", () => {
    expect(fila(web, vi.fn())).toContain("Ver texto");
  });

  it("un documento que no es web no lo muestra, y sin la acción tampoco", () => {
    expect(fila(documento, vi.fn())).not.toContain("Ver texto");
    expect(fila(web)).not.toContain("Ver texto");
  });
});
