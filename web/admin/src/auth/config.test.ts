import { describe, expect, it } from "vitest";
import { TEC_TENANT_ID, buildMsalConfig, isConfigured } from "./config";

describe("isConfigured", () => {
  it("sin client ID no está configurado", () => {
    expect(isConfigured({ origin: "http://x" })).toBe(false);
    expect(isConfigured({ origin: "http://x", clientId: "  " })).toBe(false);
    expect(isConfigured({ origin: "http://x", clientId: "abc" })).toBe(true);
  });
});

describe("buildMsalConfig", () => {
  it("usa el directorio del TEC por defecto", () => {
    const config = buildMsalConfig({ origin: "https://mia-panel.up.railway.app", clientId: "abc" });
    expect(config.auth.authority).toBe(`https://login.microsoftonline.com/${TEC_TENANT_ID}`);
    expect(config.auth.clientId).toBe("abc");
    expect(config.auth.protocolMode).toBeUndefined();
  });

  it("la dirección de redirección es el origen con una sola barra final", () => {
    expect(buildMsalConfig({ origin: "https://mia-panel.up.railway.app", clientId: "a" }).auth.redirectUri).toBe(
      "https://mia-panel.up.railway.app/",
    );
    expect(buildMsalConfig({ origin: "http://localhost:3001/", clientId: "a" }).auth.redirectUri).toBe(
      "http://localhost:3001/",
    );
  });

  it("la sesión se guarda solo para la pestaña", () => {
    expect(buildMsalConfig({ origin: "http://x", clientId: "a" }).cache?.cacheLocation).toBe("sessionStorage");
  });

  it("permite otro tenant", () => {
    const config = buildMsalConfig({ origin: "http://x", clientId: "a", tenantId: "otro" });
    expect(config.auth.authority).toBe("https://login.microsoftonline.com/otro");
  });

  it("una autoridad alternativa se describe sin consultar a Microsoft", () => {
    const config = buildMsalConfig({
      origin: "http://localhost:3001",
      clientId: "a",
      authority: "https://localhost:9000/tenant-de-prueba/",
    });
    expect(config.auth.authority).toBe("https://localhost:9000/tenant-de-prueba");
    expect(config.auth.protocolMode).toBe("OIDC");
    expect(config.auth.knownAuthorities).toEqual(["localhost:9000"]);
    const metadata = JSON.parse(config.auth.authorityMetadata!);
    expect(metadata.token_endpoint).toBe("https://localhost:9000/tenant-de-prueba/oauth2/v2.0/token");
    expect(metadata.authorization_endpoint).toBe("https://localhost:9000/tenant-de-prueba/oauth2/v2.0/authorize");
  });
});
