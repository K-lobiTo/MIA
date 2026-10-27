// @vitest-environment node
import { MantineProvider } from "@mantine/core";
import { renderToString } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { theme } from "../../theme";
import { ConfirmacionContenido, FallosContenido } from "./EliminarDocumentosDialog";
import type { DocumentoAEliminar, Fallo } from "./seleccion";

const doc = (id: string, extra: Partial<DocumentoAEliminar> = {}): DocumentoAEliminar => ({
  id,
  filename: `${id}.pdf`,
  status: "done",
  image_count: 0,
  domain_id: "d1",
  domain_name: "Admisión",
  ...extra,
});

function render(nodo: React.ReactNode): string {
  return renderToString(<MantineProvider theme={theme}>{nodo}</MantineProvider>);
}

describe("ConfirmacionContenido", () => {
  it("con un documento nombra el documento y su dominio y dice qué se pierde y que no se puede deshacer", () => {
    const html = render(<ConfirmacionContenido documentos={[doc("Maestria", { image_count: 2 })]} />);
    expect(html).toContain("Maestria.pdf");
    expect(html).toContain("Admisión");
    expect(html).toContain("bot de WhatsApp");
    expect(html).toContain("Se pierden también 2 imágenes asociadas.");
    expect(html).toContain("No se puede deshacer");
    expect(html).toContain("volver a subir el archivo original");
  });

  it("sin imágenes omite el aviso de imágenes y sin documentos en proceso omite la nota de cancelación", () => {
    const html = render(<ConfirmacionContenido documentos={[doc("a")]} />);
    expect(html).not.toContain("imagen");
    expect(html).not.toContain("Se cancelará su procesamiento");
  });

  it("con un documento en cola o procesándose avisa que se cancela su procesamiento", () => {
    expect(render(<ConfirmacionContenido documentos={[doc("a", { status: "pending" })]} />)).toContain(
      "Se cancelará su procesamiento",
    );
    expect(render(<ConfirmacionContenido documentos={[doc("a"), doc("b", { status: "processing" })]} />)).toContain(
      "Se cancelará su procesamiento",
    );
  });

  it("con más de 10 documentos lista 10 y dice cuántos más", () => {
    const quince = Array.from({ length: 15 }, (_, i) => doc(`doc${i}`));
    const html = render(<ConfirmacionContenido documentos={quince} />);
    expect(html).toContain("doc9.pdf");
    expect(html).not.toContain("doc10.pdf");
    expect(html).toContain("y 5 más");
  });
});

describe("FallosContenido", () => {
  it("lista solo los fallidos con su motivo", () => {
    const fallidos: Fallo[] = [
      { documento: doc("ajeno"), motivo: "out_of_scope", mensaje: "Está fuera de tus programas." },
      { documento: doc("ocupado"), motivo: "busy", mensaje: "Se está procesando, intenta de nuevo en un momento." },
    ];
    const html = render(<FallosContenido fallidos={fallidos} />);
    expect(html).toContain("ajeno.pdf");
    expect(html).toContain("Está fuera de tus programas.");
    expect(html).toContain("ocupado.pdf");
    expect(html).toContain("intenta de nuevo");
    expect(html).toContain("No se pudieron eliminar algunos documentos");
  });
});
