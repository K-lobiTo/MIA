// @vitest-environment node
import { MantineProvider } from "@mantine/core";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToString } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Bot, BotsResponse, Me } from "../../api/types";
import { theme } from "../../theme";

// La pantalla solo necesita el perfil de la sesión: se sustituye para no depender de MSAL ni del navegador.
let me: Me;
vi.mock("../../auth/session", () => ({ useMe: () => me }));

import { BotsPage } from "./BotsPage";

const global: Me = { email: "operador@itcr.ac.cr", is_global: true, source: "entra", units: [] };
const programa: Me = { email: "coord@itcr.ac.cr", is_global: false, source: "entra", units: [{ id: "1", name: "Computación" }] };

const bot: Bot = {
  id: "b1",
  name: "Atracción de estudiantes",
  kapso_number_id: "647015955153740",
  active: true,
  artifact: { id: "a1", name: "Bot de WhatsApp", active: true },
  domains: ["Computación / Admisión", "Computación / Plan de estudios"],
  available: true,
  unavailable_reason: null,
  usage: { received: 412, sent: 530, total: 942, cap_reached: false },
  created_at: "2026-10-24T15:30:00Z",
};

function respuesta(bots: Bot[], extra: Partial<BotsResponse> = {}): BotsResponse {
  return { monthly_cap: 1800, service_configured: true, month: "2026-10", bots, ...extra };
}

/** Renderiza la pantalla con los bots ya en la caché de TanStack Query (sin pedir nada a la API). */
function render(perfil: Me, datos: BotsResponse | null): string {
  me = perfil;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  if (datos) client.setQueryData(["bots"], datos);
  return renderToString(
    <MantineProvider theme={theme}>
      <QueryClientProvider client={client}>
        <BotsPage />
      </QueryClientProvider>
    </MantineProvider>,
  );
}

describe("BotsPage", () => {
  beforeEach(() => {
    me = global;
  });

  it("con alcance global muestra el bot, su artefacto, sus dominios y las acciones", () => {
    const html = render(global, respuesta([bot]));
    expect(html).toContain("Bots");
    expect(html).toContain("Registrar bot");
    expect(html).toContain("Atracción de estudiantes");
    expect(html).toContain("647015955153740");
    expect(html).toContain("Activo");
    expect(html).toContain("Bot de WhatsApp");
    expect(html).toContain("Computación / Admisión");
    expect(html).toContain("Computación / Plan de estudios");
    expect(html).toContain("Editar");
    expect(html).toContain("Desactivar");
    expect(html).not.toContain("BOT_SERVICE_KEY no está configurada");
    expect(html).not.toContain("Solo el alcance global puede administrar los bots");
  });

  it("un bot desactivado dice su estado y ofrece reactivarlo", () => {
    const html = render(global, respuesta([{ ...bot, active: false, available: false, unavailable_reason: "El bot está desactivado." }]));
    expect(html).toContain("Desactivado");
    expect(html).toContain("Reactivar");
  });

  it("un bot activo que no responde muestra el motivo", () => {
    const html = render(
      global,
      respuesta([{ ...bot, available: false, unavailable_reason: "El artefacto asignado está desactivado.", artifact: { id: "a1", name: "Bot de WhatsApp", active: false } }]),
    );
    expect(html).toContain("No responde");
    expect(html).toContain("El artefacto asignado está desactivado.");
    expect(html).toContain("Artefacto desactivado");
  });

  it("un bot sin artefacto lo dice", () => {
    const html = render(global, respuesta([{ ...bot, artifact: null, domains: [], available: false, unavailable_reason: "No tiene artefacto asignado." }]));
    expect(html).toContain("Sin artefacto asignado");
    expect(html).toContain("Ninguno");
  });

  it("avisa cuando BOT_SERVICE_KEY no está configurada en la API", () => {
    const html = render(global, respuesta([bot], { service_configured: false }));
    expect(html).toContain("BOT_SERVICE_KEY no está configurada en la API");
  });

  it("sin bots invita a registrar el primero", () => {
    const html = render(global, respuesta([]));
    expect(html).toContain("Todavía no hay bots registrados");
  });

  it("con alcance de programa solo muestra el aviso, sin lista ni botón de registro", () => {
    const html = render(programa, respuesta([bot]));
    expect(html).toContain("Solo el alcance global puede administrar los bots");
    expect(html).not.toContain("Registrar bot");
    expect(html).not.toContain("Atracción de estudiantes");
  });

  it("muestra el consumo del mes frente al tope con las cifras en texto", () => {
    const html = render(global, respuesta([bot]));
    expect(html).toContain("Mensajes del mes");
    expect(html).toContain("942 / 1800 mensajes (412 recibidos, 530 enviados)");
    expect(html).toContain('role="progressbar"');
    expect(html).toContain("Mensajes de octubre de 2026");
    expect(html).toContain("bot-meter-ok");
    expect(html).not.toContain("Tope mensual alcanzado");
  });

  it("cerca del tope la barra pasa a advertencia", () => {
    const html = render(global, respuesta([{ ...bot, usage: { received: 700, sent: 800, total: 1500, cap_reached: false } }]));
    expect(html).toContain("bot-meter-warn");
    expect(html).toContain("1500 / 1800 mensajes");
  });

  it("con el tope alcanzado la barra va llena, lo dice y muestra el motivo", () => {
    const html = render(
      global,
      respuesta([
        {
          ...bot,
          available: false,
          unavailable_reason: "Se alcanzó el tope mensual de mensajes.",
          usage: { received: 900, sent: 900, total: 1800, cap_reached: true },
        },
      ]),
    );
    expect(html).toContain("bot-meter-full");
    expect(html).toContain("Tope mensual alcanzado");
    expect(html).toContain("Se alcanzó el tope mensual de mensajes.");
    expect(html).toContain("No responde");
  });

  it("el tope sale de la respuesta de la API y no de un valor fijo", () => {
    const html = render(global, respuesta([bot], { monthly_cap: 2000 }));
    expect(html).toContain("942 / 2000 mensajes");
  });
});
