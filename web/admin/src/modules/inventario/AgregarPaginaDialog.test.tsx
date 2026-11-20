// @vitest-environment node
import { MantineProvider } from "@mantine/core";
import { renderToString } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { theme } from "../../theme";
import { AgregarPaginaFormulario, RechazoPagina } from "./AgregarPaginaDialog";
import { WEB_NOTICE } from "./inventoryUtils";

const render = (nodo: React.ReactNode) => renderToString(<MantineProvider theme={theme}>{nodo}</MantineProvider>);

const formulario = (extra: Partial<React.ComponentProps<typeof AgregarPaginaFormulario>> = {}) =>
  render(
    <AgregarPaginaFormulario
      destination="Currículum"
      url=""
      name=""
      error={null}
      pending={false}
      yaExistia={false}
      onUrl={vi.fn()}
      onName={vi.fn()}
      onSubmit={vi.fn()}
      onClose={vi.fn()}
      {...extra}
    />,
  );

describe("AgregarPaginaFormulario", () => {
  it("muestra el campo de dirección, el de nombre opcional, el aviso y el botón", () => {
    const html = formulario();
    expect(html).toContain("Dirección de la página");
    expect(html).toContain("Nombre (opcional)");
    expect(html).toContain("Agregar página");
    expect(html).toContain("Currículum");
    expect(html).toContain(WEB_NOTICE);
  });

  it("el aviso de datos personales se ve siempre, también con un rechazo", () => {
    const html = formulario({ error: { message: "La página requiere iniciar sesión.", code: "login_required" } });
    expect(html).toContain(WEB_NOTICE);
  });

  it("conserva lo escrito y no se cierra con un rechazo: muestra su razón", () => {
    const html = formulario({
      url: "https://ejemplo.test/privada",
      name: "Mi nombre",
      error: { message: "La página requiere iniciar sesión. Esta versión no puede leerla.", code: "login_required" },
    });
    expect(html).toContain("https://ejemplo.test/privada");
    expect(html).toContain("Mi nombre");
    expect(html).toContain("La página requiere iniciar sesión. Esta versión no puede leerla.");
    expect(html).toContain('data-code="login_required"');
  });

  it("una página que ya estaba agregada con el mismo contenido se informa y deja cerrar", () => {
    const html = formulario({ yaExistia: true });
    expect(html).toContain("Esta página ya estaba agregada con el mismo contenido.");
    expect(html).toContain("Cerrar");
  });
});

describe("página ya agregada (US5)", () => {
  const mensaje =
    "Esa página ya está agregada (leída el 20 de noviembre de 2026). Para actualizarla, elimina el documento y vuelve a agregarla.";

  it("el 409 se muestra en la ventana con la fecha y la sugerencia de eliminar y volver a agregar", () => {
    const html = formulario({ url: "https://ejemplo.test/programa", error: { message: mensaje, code: "already_added" } });
    expect(html).toContain("Esa página ya está agregada (leída el 20 de noviembre de 2026).");
    expect(html).toContain("elimina el documento y vuelve a agregarla");
    expect(html).toContain('data-code="already_added"');
    expect(html).toContain("https://ejemplo.test/programa");
  });

  it("el mismo contenido ya agregado se informa como aviso y no muestra el formulario", () => {
    const html = formulario({ yaExistia: true });
    expect(html).toContain("Esta página ya estaba agregada con el mismo contenido.");
    expect(html).not.toContain("Dirección de la página");
  });
});

describe("RechazoPagina", () => {
  it("muestra el mensaje con el tono de error y el código para las pruebas", () => {
    const html = render(<RechazoPagina message="El sitio bloquea la lectura automática." code="bot_blocked" />);
    expect(html).toContain("El sitio bloquea la lectura automática.");
    expect(html).toContain('data-code="bot_blocked"');
    expect(html).toContain('role="alert"');
  });
});
