import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// En desarrollo el servidor de Vite hace de proxy hacia la API, así el navegador no necesita CORS.
// Publicado como sitio estático, la API debe permitir su origen (CORS_ORIGINS). MIA_API_URL permite
// apuntar a otra instancia (p. ej. Railway).
const apiUrl = process.env.MIA_API_URL ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3001,
    strictPort: true,
    proxy: {
      "/api": {
        target: apiUrl,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
        // Una consulta con razonamiento o una API dormida pueden tardar.
        timeout: 200_000,
        proxyTimeout: 200_000,
      },
    },
  },
  preview: { port: 3001, strictPort: true },
});
