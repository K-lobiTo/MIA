import type { Configuration } from "@azure/msal-browser";

// Directorio (tenant) del TEC: es público y fijo; solo el client ID lo entrega TI.
export const TEC_TENANT_ID = "1119bb90-88ba-4894-b7f1-de26e129d977";
export const LOGIN_SCOPES = ["openid", "profile", "email"];

export interface EntraEnv {
  clientId?: string;
  tenantId?: string;
  // Solo desarrollo: autoridad alternativa (servidor de identidad simulado, scripts/idp_simulado.py).
  authority?: string;
  // Origen del sitio; la dirección de redirección es el origen con barra final, como en la solicitud a TI.
  origin: string;
}

export function isConfigured(env: EntraEnv): boolean {
  return Boolean(env.clientId?.trim());
}

/** Configuración de MSAL a partir de las variables de compilación. La sesión vive en sessionStorage:
 * solo la pestaña abierta, nada persistente. */
export function buildMsalConfig(env: EntraEnv): Configuration {
  const clientId = (env.clientId ?? "").trim();
  const redirectUri = `${env.origin.replace(/\/+$/, "")}/`;
  const custom = env.authority?.trim().replace(/\/+$/, "");
  const cache = { cacheLocation: "sessionStorage" };

  if (!custom) {
    const tenant = env.tenantId?.trim() || TEC_TENANT_ID;
    return {
      auth: { clientId, authority: `https://login.microsoftonline.com/${tenant}`, redirectUri },
      cache,
    };
  }
  // Autoridad que no es Microsoft: se describe en la configuración para que MSAL no consulte a nadie.
  return {
    auth: {
      clientId,
      authority: custom,
      redirectUri,
      protocolMode: "OIDC",
      knownAuthorities: [new URL(custom).host],
      authorityMetadata: JSON.stringify({
        issuer: `${custom}/v2.0`,
        authorization_endpoint: `${custom}/oauth2/v2.0/authorize`,
        token_endpoint: `${custom}/oauth2/v2.0/token`,
        end_session_endpoint: `${custom}/oauth2/v2.0/logout`,
        jwks_uri: `${custom}/discovery/v2.0/keys`,
      }),
    },
    cache,
  };
}
