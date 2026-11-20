// @vitest-environment node
import { MantineProvider } from "@mantine/core";
import { renderToString } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { theme } from "../../theme";
import { TextoDocumentoContenido } from "./TextoDocumentoDialog";

const render = (props: Partial<React.ComponentProps<typeof TextoDocumentoContenido>> = {}) =>
  renderToString(
    <MantineProvider theme={theme}>
      <TextoDocumentoContenido
        filename="Maestría de Ejemplo"
        text={"Fuente: https://ejemplo.test/programa (consultada el 20 de noviembre de 2026)\nMaestría de Ejemplo\n\nContenido"}
        sourceUrl="https://ejemplo.test/programa"
        readAt="2026-11-20T15:04:05"
        onClose={vi.fn()}
        {...props}
      />
    </MantineProvider>,
  );

describe("TextoDocumentoContenido", () => {
  it("muestra el texto, la dirección con su enlace seguro, la fecha de lectura y el botón Cerrar", () => {
    const html = render();
    expect(html).toContain("Fuente: https://ejemplo.test/programa (consultada el 20 de noviembre de 2026)");
    expect(html).toContain('href="https://ejemplo.test/programa"');
    expect(html).toContain('rel="noopener noreferrer"');
    expect(html).toContain("leída el");
    expect(html).toContain("Cerrar");
  });

  it("muestra el texto como texto plano: lo que traiga la página no se interpreta como HTML", () => {
    const html = render({ text: "<b>hola</b> <script>alert(1)</script>" });
    expect(html).toContain("&lt;b&gt;hola&lt;/b&gt;");
    expect(html).not.toContain("<script>alert(1)</script>");
    expect(html).toContain("pre-wrap");
  });

  it("una dirección que no es http ni https no se vuelve enlace", () => {
    expect(render({ sourceUrl: "javascript:alert(1)" })).not.toContain("javascript:alert(1)");
  });
});
