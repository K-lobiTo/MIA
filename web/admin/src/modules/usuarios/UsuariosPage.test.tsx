// @vitest-environment node
import { MantineProvider } from "@mantine/core";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToString } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ConsultaUser, ConsultaUsersResponse, Me } from "../../api/types";
import { theme } from "../../theme";

// La pantalla solo necesita el perfil de la sesión: se sustituye para no depender de MSAL ni del navegador.
let me: Me;
vi.mock("../../auth/session", () => ({ useMe: () => me }));

import { UsuariosPage } from "./UsuariosPage";

const global: Me = { email: "operador@itcr.ac.cr", is_global: true, source: "entra", units: [] };

const ana: ConsultaUser = {
  id: "u1",
  username: "ana.perez",
  unit: { id: "p1", name: "Unidad de Postgrados de Computación" },
  active: true,
  created_at: "2026-11-04T15:30:00Z",
  last_login_at: "2026-11-04T16:02:00Z",
  conversation_count: 3,
  last_activity_at: "2026-11-04T16:20:00Z",
};

function render(datos: ConsultaUsersResponse | null): string {
  me = global;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  if (datos) client.setQueryData(["consulta-users"], datos);
  return renderToString(
    <MantineProvider theme={theme}>
      <QueryClientProvider client={client}>
        <UsuariosPage />
      </QueryClientProvider>
    </MantineProvider>,
  );
}

describe("UsuariosPage", () => {
  beforeEach(() => {
    me = global;
  });

  it("lista el usuario con su estado, programa, último acceso y cantidad de conversaciones", () => {
    const html = render({ users: [ana] });
    expect(html).toContain("Usuarios de la Consulta");
    expect(html).toContain("Registrar usuario");
    expect(html).toContain("ana.perez");
    expect(html).toContain("Activo");
    expect(html).toContain("Unidad de Postgrados de Computación");
    expect(html).toContain("3 conversaciones");
    expect(html).toContain("Desactivar");
    expect(html).toContain("Restablecer contraseña");
  });

  it("un usuario desactivado ofrece reactivarlo y uno sin programa dice global", () => {
    const html = render({ users: [{ ...ana, active: false, unit: null, conversation_count: 0, last_activity_at: null, last_login_at: null }] });
    expect(html).toContain("Desactivado");
    expect(html).toContain("Reactivar");
    expect(html).toContain("Ninguno (global)");
    expect(html).toContain("Sin conversaciones guardadas");
    expect(html).toContain("Nunca");
  });

  it("nunca muestra una contraseña ni su hash y dice que la administración no puede leer las conversaciones", () => {
    const html = render({ users: [ana] });
    expect(html).not.toContain("scrypt");
    expect(html).not.toContain("contrasena-completa");
    expect(html).toContain("quien administra no puede leerlas");
  });

  it("sin usuarios invita a registrar el primero", () => {
    expect(render({ users: [] })).toContain("Todavía no hay usuarios registrados");
  });
});
