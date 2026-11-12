// @vitest-environment node
import { MantineProvider } from "@mantine/core";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToString } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Contact, ContactsResponse, Me } from "../../api/types";
import { theme } from "../../theme";

// La pantalla solo necesita el perfil de la sesión: se sustituye para no depender de MSAL ni del navegador.
let me: Me;
vi.mock("../../auth/session", () => ({ useMe: () => me }));

import { ContactosPage } from "./ContactosPage";

const global: Me = { email: "operador@itcr.ac.cr", is_global: true, source: "entra", units: [] };
const programa: Me = { email: "coord@itcr.ac.cr", is_global: false, source: "entra", units: [{ id: "1", name: "Computación" }] };

const ana: Contact = {
  id: "c1",
  phone: "+50688887777",
  bot: { id: "b1", name: "Posgrados computación" },
  name: "Ana Pérez",
  email: "ana@correo.com",
  status: "entrego",
  created_at: "2026-11-12T15:04:05Z",
  last_seen_at: "2026-11-12T15:10:00Z",
  updated_at: "2026-11-12T15:05:30Z",
};
const luis: Contact = { ...ana, id: "c2", phone: "+50670001111", name: null, email: null, status: "declino" };

function respuesta(items: Contact[], extra: Partial<ContactsResponse> = {}): ContactsResponse {
  return {
    total: items.length,
    page: 1,
    page_size: 50,
    items,
    summary: { pendiente: 0, invitada: 1, entrego: 40, declino: 91 },
    ...extra,
  };
}

/** Renderiza la pantalla con la lista ya en la caché de TanStack Query (sin pedir nada a la API). */
function render(perfil: Me, datos: ContactsResponse | null): string {
  me = perfil;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  // Sin filtros elegidos, la clave es la de los filtros vacíos y la página 1.
  if (datos) client.setQueryData(["contacts", { status: [] }, 1], datos);
  return renderToString(
    <MantineProvider theme={theme}>
      <QueryClientProvider client={client}>
        <ContactosPage />
      </QueryClientProvider>
    </MantineProvider>,
  );
}

describe("ContactosPage", () => {
  beforeEach(() => {
    me = global;
  });

  it("con alcance global muestra los contactos con teléfono, nombre, correo, estado, y los totales por estado", () => {
    const html = render(global, respuesta([ana, luis]));
    expect(html).toContain("Contactos de WhatsApp");
    expect(html).toContain("+506 8888-7777");
    expect(html).toContain("Ana Pérez");
    expect(html).toContain("ana@correo.com");
    expect(html).toContain("Posgrados computación");
    expect(html).toContain("Dejó sus datos");
    expect(html).toContain("No quiso dejar datos");
    // Los totales por estado vienen de `summary`.
    expect(html).toContain("40");
    expect(html).toContain("91");
    expect(html).toContain("Descargar CSV");
    expect(html).toContain("Borrar los 2");
  });

  it("lo que no se entregó se muestra como sin nombre y sin correo", () => {
    const html = render(global, respuesta([luis]));
    expect(html).toContain("sin nombre");
    expect(html).toContain("sin correo");
  });

  it("deja ver que son datos personales y que cada descarga y borrado queda registrado", () => {
    const html = render(global, respuesta([ana]));
    expect(html).toContain("datos personales");
    expect(html).toContain("queda registrado");
  });

  it("tiene los filtros por bot, estado y correo", () => {
    const html = render(global, respuesta([ana]));
    expect(html).toContain("Bot");
    expect(html).toContain("Estado");
    expect(html).toContain("Correo");
  });

  it("sin contactos muestra el estado vacío y no ofrece descargar ni borrar", () => {
    const html = render(global, respuesta([], { total: 0, summary: { pendiente: 0, invitada: 0, entrego: 0, declino: 0 } }));
    expect(html).toContain("Todavía no hay contactos");
    expect(html).toMatch(/Descargar CSV/);
    expect(html).toMatch(/disabled/);
  });

  it("mientras carga muestra el aviso de carga", () => {
    expect(render(global, null)).toContain("Cargando contactos");
  });

  it("una cuenta de programa solo ve el aviso de alcance y ningún contacto", () => {
    const html = render(programa, respuesta([ana]));
    expect(html).toContain("Solo el alcance global");
    expect(html).not.toContain("+506 8888-7777");
    expect(html).not.toContain("ana@correo.com");
  });
});
