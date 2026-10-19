// @vitest-environment node
import { MantineProvider } from "@mantine/core";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToString } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { EquivalencesResponse, Me } from "../../api/types";
import { theme } from "../../theme";

// La pantalla solo necesita el perfil de la sesión: se sustituye para no depender de MSAL ni del navegador.
let me: Me;
vi.mock("../../auth/session", () => ({ useMe: () => me }));

import { EquivalenciasPage } from "./EquivalenciasPage";

const global: Me = { email: "operador@itcr.ac.cr", is_global: true, source: "entra", units: [] };
const programa: Me = { email: "coord@itcr.ac.cr", is_global: false, source: "entra", units: [{ id: "1", name: "Computación" }] };

const lista: EquivalencesResponse = {
  equivalences: [
    { id: "1", sigla: "MGTI", form: "Gestión de Tecnologías de Información", created_by: "automatizacion", created_at: "2026-10-19T12:00:00", updated_by: null, updated_at: null },
    { id: "2", sigla: "TFG", form: "Trabajo Final de Graduación", created_by: "automatizacion", created_at: "2026-10-19T12:00:00", updated_by: null, updated_at: null },
  ],
};

/** Renderiza la pantalla con la lista ya en la caché de TanStack Query (sin pedir nada a la API). */
function render(perfil: Me, datos: EquivalencesResponse | null = lista): string {
  me = perfil;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  if (datos) client.setQueryData(["equivalences"], datos);
  return renderToString(
    <MantineProvider theme={theme}>
      <QueryClientProvider client={client}>
        <EquivalenciasPage />
      </QueryClientProvider>
    </MantineProvider>,
  );
}

describe("EquivalenciasPage", () => {
  beforeEach(() => {
    me = global;
  });

  it("con alcance global muestra la tabla y los botones de escritura", () => {
    const html = render(global);
    expect(html).toContain("Siglas y equivalencias");
    expect(html).toContain("Agregar equivalencia");
    expect(html).toContain("TFG");
    expect(html).toContain("Trabajo Final de Graduación");
    expect(html).toContain("MGTI");
    expect(html).toContain("Editar TFG");
    expect(html).toContain("Borrar TFG");
    expect(html).not.toContain("Solo el alcance global puede agregar");
  });

  it("con alcance de programa muestra la tabla y el aviso, sin ningún botón de escritura", () => {
    const html = render(programa);
    expect(html).toContain("TFG");
    expect(html).toContain("Gestión de Tecnologías de Información");
    expect(html).toContain("Solo el alcance global puede agregar, editar o borrar equivalencias");
    expect(html).not.toContain("Agregar equivalencia");
    expect(html).not.toContain("Editar TFG");
    expect(html).not.toContain("Borrar TFG");
  });

  it("explica el efecto de la lista y que sin la búsqueda híbrida no tiene efecto", () => {
    const html = render(global);
    expect(html).toContain("también busca su forma desarrollada");
    expect(html).toContain("menos de un minuto");
    expect(html).toContain("la lista no tiene");
  });

  it("con la lista vacía invita a agregar la primera solo a quien puede", () => {
    expect(render(global, { equivalences: [] })).toContain("Todavía no hay equivalencias");
    expect(render(global, { equivalences: [] })).toContain("Agrega la primera");
    expect(render(programa, { equivalences: [] })).not.toContain("Agrega la primera");
  });

  it("mientras carga muestra el estado de carga y ningún botón de escritura de filas", () => {
    const html = render(global, null);
    expect(html).toContain("Cargando equivalencias");
    expect(html).not.toContain("Editar TFG");
  });
});
