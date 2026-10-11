import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { HashRouter } from "react-router-dom";
import { fetchMe } from "./api/me";
import { App } from "./App";
import { initSession, loadProfile } from "./auth/session";
import "./styles/tokens.css";
import "./styles/base.css";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
});

async function start() {
  // Primero la sesión: la respuesta de Microsoft llega en el fragmento de la dirección (#code=...) y
  // MSAL debe procesarla y limpiarla antes de que el router la lea.
  await initSession();
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        {/* HashRouter: funciona en un sitio estático sin configurar reescrituras. */}
        <HashRouter>
          <App />
        </HashRouter>
      </QueryClientProvider>
    </StrictMode>,
  );
  void loadProfile(fetchMe);
}

void start();
