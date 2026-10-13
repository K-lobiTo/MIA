import { MantineProvider } from "@mantine/core";
import { DatesProvider } from "@mantine/dates";
import dayjs from "dayjs";
import "dayjs/locale/es";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { HashRouter } from "react-router-dom";
import { fetchMe } from "./api/me";
import { App } from "./App";
import { theme } from "./theme";
import { initSession, loadProfile } from "./auth/session";
// Los estilos de Mantine van en una capa de CSS (`@layer`): los propios, que no están en capa, prevalecen
// siempre, sin importar en qué orden se carguen los archivos.
import "@mantine/core/styles.layer.css";
import "@mantine/dates/styles.layer.css";
import "./styles/tokens.css";
import "./styles/base.css";

// Fechas del selector de rango en español, con la semana desde el lunes.
dayjs.locale("es");

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
});

async function start() {
  // Primero la sesión: la respuesta de Microsoft llega en el fragmento de la dirección (#code=...) y
  // MSAL debe procesarla y limpiarla antes de que el router la lea.
  await initSession();
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      {/* "auto": sigue el modo claro u oscuro del sistema, igual que los colores de styles/tokens.css. */}
      <MantineProvider theme={theme} defaultColorScheme="auto">
        <DatesProvider settings={{ locale: "es", firstDayOfWeek: 1 }}>
          <QueryClientProvider client={queryClient}>
            {/* HashRouter: funciona en un sitio estático sin configurar reescrituras. */}
            <HashRouter>
              <App />
            </HashRouter>
          </QueryClientProvider>
        </DatesProvider>
      </MantineProvider>
    </StrictMode>,
  );
  void loadProfile(fetchMe);
}

// MSAL abre un iframe oculto con esta misma dirección para renovar la sesión en silencio. Dentro de él no
// se monta el panel: la ventana principal solo necesita leer la respuesta de Microsoft en la dirección.
if (window.self === window.top) void start();
