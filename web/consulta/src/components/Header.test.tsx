// @vitest-environment node
import { AppShell, MantineProvider } from "@mantine/core";
import { renderToString } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { theme } from "../theme";
import { Header } from "./Header";

function render(open: boolean): string {
  return renderToString(
    <MantineProvider theme={theme}>
      <AppShell header={{ height: 56 }}>
        <Header
          name="Consulta de prueba"
          sidebarOpen={false}
          onToggleSidebar={vi.fn()}
          desktopSidebarOpen={open}
          onToggleDesktopSidebar={vi.fn()}
        />
      </AppShell>
    </MantineProvider>,
  );
}

describe("Header", () => {
  it("muestra el logo del TEC y el nombre de la instancia", () => {
    const html = render(true);
    expect(html).toContain('alt="Tecnológico de Costa Rica"');
    expect(html).toContain('src="/logoTec.png"');
    expect(html).toContain("Consulta de prueba");
  });

  it("el botón del menú lateral dice qué hará según su estado", () => {
    expect(render(true)).toContain("Ocultar el menú lateral");
    expect(render(false)).toContain("Mostrar el menú lateral");
  });
});
