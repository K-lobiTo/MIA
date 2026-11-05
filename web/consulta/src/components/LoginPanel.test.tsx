// @vitest-environment node
import { MantineProvider } from "@mantine/core";
import { renderToString } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { theme } from "../theme";
import { LoginPanel } from "./LoginPanel";

function render(props: Partial<React.ComponentProps<typeof LoginPanel>> = {}): string {
  return renderToString(
    <MantineProvider theme={theme}>
      <LoginPanel busy={false} error={null} onSubmit={vi.fn()} {...props} />
    </MantineProvider>,
  );
}

describe("LoginPanel", () => {
  it("pide usuario y contraseña", () => {
    const html = render();
    expect(html).toContain("Usuario");
    expect(html).toContain("Contraseña");
    expect(html).toContain("Iniciar sesión");
  });

  it("muestra el error que se le pasa", () => {
    expect(render({ error: "Usuario o contraseña incorrectos." })).toContain("Usuario o contraseña incorrectos.");
  });

  it("dice cuántos días se guardan las conversaciones cuando se informa la retención", () => {
    const html = render({ retentionDays: 90 });
    expect(html).toContain("90 días");
    expect(html).toContain("borrarlas");
  });

  it("sin retención (guardado apagado) no promete guardar nada", () => {
    expect(render({ retentionDays: 0 })).not.toContain("días");
  });

  it("a pantalla completa avisa que la Consulta exige iniciar sesión", () => {
    expect(render({ required: true })).toContain("exige iniciar sesión");
  });
});
