/// <reference types="vite/client" />

interface ImportMetaEnv {
  // URL de la API al publicar como sitio estático (en desarrollo se usa el proxy /api de Vite).
  readonly VITE_API_URL?: string;
}
