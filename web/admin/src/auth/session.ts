import { PublicClientApplication, type AccountInfo, type AuthenticationResult } from "@azure/msal-browser";
import { useSyncExternalStore } from "react";
import type { Me } from "../api/types";
import { LOGIN_SCOPES, buildMsalConfig, isConfigured, type EntraEnv } from "./config";
import { BROWSER_BLOCKED, EXPIRED, microsoftProblem, type AccessProblem } from "./errors";

// Estado de acceso del panel. Solo este módulo conoce a MSAL; el resto usa estas funciones.
export type AccessState =
  | { kind: "cargando" }
  | { kind: "sin_sesion" }
  | { kind: "no_configurado" }
  | { kind: "iniciando" }
  | { kind: "activa"; me: Me }
  | { kind: "rechazada"; problem: AccessProblem };

let state: AccessState = { kind: "cargando" };
const listeners = new Set<() => void>();

function setState(next: AccessState): void {
  state = next;
  listeners.forEach((listener) => listener());
}

export function useAccessState(): AccessState {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    () => state,
  );
}

/** El perfil de la sesión activa. Solo se usa dentro del panel, que se muestra únicamente con sesión. */
export function useMe(): Me {
  const current = useAccessState();
  if (current.kind !== "activa") throw new Error("No hay una sesión activa.");
  return current.me;
}

export class NoSessionError extends Error {}

const RENEW_MARGIN_SECONDS = 5 * 60;
const LEGACY_KEY = "mia-admin-key";
// La clave de administración (ADMIN_KEY, alcance global) es una segunda forma de entrar, para cuando no hay
// cuenta del TEC. Vive solo en la pestaña (sessionStorage), nunca en localStorage.
const KEY_STORAGE = "mia-clave-sesion";

let adminKey = "";
let msal: PublicClientApplication | null = null;
let account: AccountInfo | null = null;
// Con solo los permisos openid, profile y email, MSAL no guarda un token de acceso que reutilizar:
// cada llamada iría a Microsoft. Por eso se guarda aquí el token de identidad vigente y se renueva
// cuando faltan menos de 5 minutos para que venza.
let cached: { token: string; exp: number } | null = null;
let renewing: Promise<string> | null = null;

function readEnv(): EntraEnv {
  return {
    clientId: import.meta.env.VITE_ENTRA_CLIENT_ID,
    tenantId: import.meta.env.VITE_ENTRA_TENANT_ID,
    authority: import.meta.env.VITE_ENTRA_AUTHORITY,
    origin: window.location.origin,
  };
}

function remember(result: AuthenticationResult): string {
  const claims = result.idTokenClaims as { exp?: number } | undefined;
  const exp = Number(claims?.exp ?? 0) || Date.now() / 1000 + 3000;
  cached = { token: result.idToken, exp };
  return result.idToken;
}

function readStoredKey(): string {
  try {
    return sessionStorage.getItem(KEY_STORAGE) ?? "";
  } catch {
    return "";
  }
}

function storeKey(key: string): void {
  adminKey = key;
  try {
    if (key) sessionStorage.setItem(KEY_STORAGE, key);
    else sessionStorage.removeItem(KEY_STORAGE);
  } catch {
    // sin almacenamiento: la clave queda solo en memoria
  }
}

/** La clave de administración con que se entró, o "" si se entró con una cuenta del TEC. */
export function getAdminKey(): string {
  return adminKey;
}

export function usingKey(): boolean {
  return adminKey !== "";
}

function clearLegacyKey(): void {
  // La clave compartida de la versión anterior ya no se usa: se borra del navegador.
  try {
    localStorage.removeItem(LEGACY_KEY);
  } catch {
    // sin almacenamiento: nada que borrar
  }
}

/** Prepara MSAL y resuelve la redirección de Microsoft, si venimos de ella. Debe terminar antes de
 * que el router lea la dirección: la respuesta de Microsoft llega en el fragmento (#code=...). */
export async function initSession(): Promise<void> {
  clearLegacyKey();
  const env = readEnv();
  adminKey = readStoredKey();
  if (adminKey) return; // sesión con la clave de administración de esta pestaña
  if (!isConfigured(env)) {
    setState({ kind: "no_configurado" });
    return;
  }
  try {
    msal = new PublicClientApplication(buildMsalConfig(env));
    await msal.initialize();
  } catch {
    setState({ kind: "rechazada", problem: BROWSER_BLOCKED });
    return;
  }
  try {
    const result = await msal.handleRedirectPromise();
    if (result) remember(result);
    account = result?.account ?? msal.getActiveAccount() ?? msal.getAllAccounts()[0] ?? null;
  } catch (caught) {
    const detail = caught instanceof Error ? caught.message.split(":").pop()?.trim() : undefined;
    setState({ kind: "rechazada", problem: microsoftProblem(detail) });
    return;
  }
  if (account) msal.setActiveAccount(account);
  else setState({ kind: "sin_sesion" });
}

/** Con una cuenta ya conocida, pide el perfil a la API para pasar al panel. Los rechazos de acceso
 * ya los registra el cliente de la API con `reject`. */
export async function loadProfile(loadMe: () => Promise<Me>): Promise<void> {
  if (!account && !usingKey()) return;
  try {
    setState({ kind: "activa", me: await loadMe() });
  } catch (caught) {
    if (state.kind !== "rechazada") {
      const message = caught instanceof Error ? caught.message : "No se pudo cargar tu perfil.";
      setState({ kind: "rechazada", problem: { kind: "identidad_no_disponible", message, action: "reintentar" } });
    }
  }
}

/** Entra con la clave de administración: la valida pidiendo el perfil a la API (alcance global). */
export async function signInWithKey(key: string, loadMe: () => Promise<Me>): Promise<void> {
  storeKey(key.trim());
  setState({ kind: "cargando" });
  await loadProfile(loadMe);
  if (state.kind !== "activa") storeKey(""); // clave incorrecta u otro fallo: no se recuerda
}

/** Vuelve a la pantalla de entrada (por ejemplo tras una clave incorrecta). */
export function backToLogin(): void {
  storeKey("");
  setState(isConfigured(readEnv()) ? { kind: "sin_sesion" } : { kind: "no_configurado" });
}

export function currentEmail(): string | undefined {
  return account?.username;
}

export function reject(problem: AccessProblem): void {
  setState({ kind: "rechazada", problem });
}

export async function signIn(forceLogin = false): Promise<void> {
  if (!msal) return;
  setState({ kind: "iniciando" });
  try {
    await msal.loginRedirect({ scopes: LOGIN_SCOPES, prompt: forceLogin ? "login" : undefined });
  } catch (caught) {
    const detail = caught instanceof Error ? caught.message.split(":").pop()?.trim() : undefined;
    setState({ kind: "rechazada", problem: microsoftProblem(detail) });
  }
}

/** Cierra la sesión solo en este navegador: borra la caché local sin cerrar la sesión de Microsoft. */
export async function signOut(): Promise<void> {
  if (usingKey()) {
    backToLogin();
    return;
  }
  cached = null;
  const current = account;
  account = null;
  try {
    if (msal && current) await msal.logoutRedirect({ account: current, onRedirectNavigate: () => false });
  } catch {
    // aun así la sesión local queda cerrada
  }
  try {
    sessionStorage.clear();
  } catch {
    // sin almacenamiento
  }
  setState(isConfigured(readEnv()) ? { kind: "sin_sesion" } : { kind: "no_configurado" });
}

/** Token de identidad vigente para enviar a la API; lo renueva en silencio si está por vencer o se
 * pide `force`. Lanza NoSessionError si no se puede (la sesión de Microsoft venció o fue revocada). */
export async function getIdToken(force = false): Promise<string> {
  if (!msal || !account) throw new NoSessionError();
  if (!force && cached && cached.exp - Date.now() / 1000 > RENEW_MARGIN_SECONDS) return cached.token;
  if (!renewing) {
    const client = msal;
    const who = account;
    renewing = client
      .acquireTokenSilent({ scopes: LOGIN_SCOPES, account: who, forceRefresh: true })
      .then(remember)
      .catch(() => {
        cached = null;
        throw new NoSessionError();
      })
      .finally(() => {
        renewing = null;
      });
  }
  return renewing;
}

export { EXPIRED };
