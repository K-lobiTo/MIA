import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// En desarrollo el servidor de Vite hace de proxy hacia la API, así el navegador no necesita CORS.
// Publicado como sitio estático, la API debe permitir su origen (CORS_ORIGINS) y la compilación
// lleva VITE_API_URL. MIA_API_URL permite apuntar a otra instancia (p. ej. Railway).
const apiUrl = process.env.MIA_API_URL ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    strictPort: true,
    proxy: {
      "/api": {
        target: apiUrl,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
        // Una consulta con razonamiento puede tardar decenas de segundos.
        timeout: 200_000,
        proxyTimeout: 200_000,
      },
    },
  },
  preview: { port: 3000, strictPort: true },
});
