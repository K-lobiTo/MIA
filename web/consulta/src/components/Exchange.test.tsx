// @vitest-environment node
import { MantineProvider } from "@mantine/core";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToString } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import type { Exchange as ExchangeData } from "../state/conversation";
import { theme } from "../theme";
import { Exchange } from "./Exchange";

function intercambio(parcial: Partial<ExchangeData> = {}): ExchangeData {
  return {
    localId: "l1",
    question: "¿Cuántos créditos tiene el curso?",
    domainIds: ["d1"],
    mode: "literal",
    status: "answered",
    response: {
      id: "q1",
      answer: "Tiene 4 créditos.",
      sources: [
        { domain: "Currículum", document: "Curso A.docx", excerpt: "Créditos: 4" },
        { domain: "Currículum", document: "Curso B.docx", excerpt: "Créditos: 3" },
      ],
      mode: "literal",
      latency_ms: 1200,
      no_info: false,
    },
    ...parcial,
  } as ExchangeData;
}

function render(exchange: ExchangeData): string {
  const html = renderToString(
    <QueryClientProvider client={new QueryClient()}>
      <MantineProvider theme={theme}>
        <Exchange
          exchange={exchange}
          onRetry={vi.fn()}
          literalAvailable
          busy={false}
          modeNames={{ literal: "Literal", razonamiento: "Con razonamiento" }}
          onRate={vi.fn()}
        />
      </MantineProvider>
    </QueryClientProvider>,
  );
  // React separa los textos con comentarios al renderizar en el servidor.
  return html.replace(/<!-- -->/g, "");
}

describe("Exchange", () => {
  it("una respuesta lleva el avatar de MIA, las fuentes, los fragmentos y el botón de copiar", () => {
    const html = render(intercambio());
    expect(html).toContain("Tiene 4 créditos.");
    expect(html).toContain('alt="MIA"');
    expect(html).toContain("Fuentes");
    expect(html).toContain("Curso A.docx");
    expect(html).toContain("Ver fragmentos (2)");
    expect(html).toContain('aria-label="Copiar respuesta"');
    expect(html).toContain("Literal");
  });

  it("la pregunta de la persona va en su propia burbuja", () => {
    const html = render(intercambio());
    expect(html).toContain("message-row user");
    expect(html).toContain("¿Cuántos créditos tiene el curso?");
  });

  it("las burbujas nuevas entran con animación y las de una conversación guardada no", () => {
    expect(render(intercambio())).toMatch(/message-row[^"]* enter/);
    expect(render(intercambio({ stored: true }))).not.toMatch(/message-row[^"]* enter/);
  });

    it("una conversación guardada sin fragmentos no ofrece 'Ver fragmentos'", () => {
    const base = intercambio();
    const html = render({
      ...base,
      stored: true,
      response: { ...base.response!, sources: [{ domain: "Currículum", document: "Curso A.docx", excerpt: "" }] },
    });
    expect(html).toContain("Curso A.docx");
    expect(html).not.toContain("Ver fragmentos");
  });

  it("mientras busca muestra el indicador y el aviso del modo con razonamiento", () => {
    const html = render(intercambio({ status: "pending", response: undefined, mode: "razonamiento" }));
    expect(html).toContain("Buscando en 1 dominio");
    expect(html).toContain("puede tardar más de un minuto");
  });
});
