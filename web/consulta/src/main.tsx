import { MantineProvider } from "@mantine/core";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { theme } from "./theme";
// Los estilos de Mantine van en una capa de CSS (`@layer`): los propios, que no están en capa, prevalecen
// siempre, sin importar en qué orden se carguen los archivos.
import "@mantine/core/styles.layer.css";
import "./styles/tokens.css";
import "./styles/base.css";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    {/* "auto": sigue el modo claro u oscuro del sistema, salvo que se elija otro con el interruptor. */}
    <MantineProvider theme={theme} defaultColorScheme="auto">
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </MantineProvider>
  </StrictMode>,
);
