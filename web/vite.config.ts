import { defineConfig } from "vite";

// La API no tiene CORS configurado: el servidor de Vite hace de proxy y el navegador solo habla
// con localhost:3000. MIA_API_URL permite apuntar a otra instancia (p. ej. la API local).
const apiUrl = process.env.MIA_API_URL ?? "https://mia-api-5qgh.onrender.com";

export default defineConfig({
  server: {
    port: 3000,
    strictPort: true,
    proxy: {
      "/api": {
        target: apiUrl,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
        // Las respuestas pueden tardar: Render dormido (~1 min) y Gemini (5-30 s o más).
        timeout: 200_000,
        proxyTimeout: 200_000,
      },
    },
  },
  preview: { port: 3000, strictPort: true },
});
