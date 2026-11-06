// @vitest-environment node
import { MantineProvider } from "@mantine/core";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToString } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { theme } from "../theme";
import { Conversation } from "./Conversation";

function render(props: Partial<React.ComponentProps<typeof Conversation>> = {}): string {
  return renderToString(
    <QueryClientProvider client={new QueryClient()}>
      <MantineProvider theme={theme}>
        <Conversation
          exchanges={[]}
          onRetry={vi.fn()}
          literalAvailable
          busy={false}
          mode="literal"
          modeNames={{ literal: "Literal" }}
          onRate={vi.fn()}
          {...props}
        />
      </MantineProvider>
    </QueryClientProvider>,
  ).replace(/<!-- -->/g, "");
}

describe("Conversation", () => {
  it("vacía invita a preguntar y, con onExample, los ejemplos son botones", () => {
    const html = render({ onExample: vi.fn() });
    expect(html).toContain("Pregunta sobre los documentos de tu programa");
    expect(html).toContain("toca un ejemplo para escribirlo");
    expect(html).toContain("<button");
  });

  it("sin onExample los ejemplos son solo texto", () => {
    const html = render();
    expect(html).toContain("Por ejemplo:");
    expect(html).not.toContain("<button");
  });

  it("los botones de saltar no aparecen hasta que haya conversación fuera de la vista", () => {
    const html = render();
    expect(html).not.toContain("Ir al primer mensaje");
    expect(html).not.toContain("Ir al último mensaje");
    expect(html).toContain("scroll-buttons");
  });
});
