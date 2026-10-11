/// <reference types="vite/client" />

interface ImportMetaEnv {
  // URL de la API al publicar como sitio estático (en desarrollo se usa el proxy /api de Vite).
  readonly VITE_API_URL?: string;
  // Identificador de la aplicación registrada en el directorio del TEC (lo entrega TI). Sin él, el panel
  // arranca pero muestra que el inicio de sesión no está configurado.
  readonly VITE_ENTRA_CLIENT_ID?: string;
  // Directorio (tenant); por defecto el del TEC.
  readonly VITE_ENTRA_TENANT_ID?: string;
  // Solo desarrollo: autoridad alternativa (servidor de identidad simulado).
  readonly VITE_ENTRA_AUTHORITY?: string;
}
