import type { ConsultaUser } from "../../api/types";
import type { BadgeTone } from "../../components/StatusBadge";

export const MIN_PASSWORD = 10;
export const USERNAME_RULE =
  "El usuario tiene de 3 a 40 caracteres: letras minúsculas sin tilde, números, punto, guion y guion bajo.";
export const PRIVACY_TEXT =
  "Las personas con usuario guardan sus conversaciones en el servidor y quien administra no puede leerlas: aquí solo se ve cuántas tienen y cuándo fue la última.";
export const ONE_TIME_PASSWORD_TEXT =
  "Esta contraseña se muestra una sola vez. Entrégala a la persona; no se podrá volver a ver.";

export function normalizeUsername(text: string): string {
  return text.trim().toLowerCase();
}

/** El motivo por el que el nombre no sirve (ya normalizado), o null si cumple. La API es quien hace cumplir la regla. */
export function validateUsername(text: string): string | null {
  return /^[a-z0-9._-]{3,40}$/.test(normalizeUsername(text)) ? null : USERNAME_RULE;
}

/** El motivo por el que una contraseña escrita no sirve, o null; vacía vale (el servidor genera una). */
export function validatePassword(text: string): string | null {
  if (text === "") return null;
  if (text.trim() === "") return "La contraseña no puede ser solo espacios.";
  return text.length < MIN_PASSWORD ? `La contraseña tiene al menos ${MIN_PASSWORD} caracteres.` : null;
}

const ALPHABET = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789";

/** Una contraseña aleatoria de 16 caracteres legibles (sin los que se confunden). `random` permite probarla. */
export function generatePassword(random: (n: number) => number[] = randomValues, length = 16): string {
  return random(length)
    .map((n) => ALPHABET[n % ALPHABET.length])
    .join("");
}

function randomValues(n: number): number[] {
  const bytes = new Uint32Array(n);
  crypto.getRandomValues(bytes);
  return Array.from(bytes);
}

/** Estado del usuario en una etiqueta: el texto siempre lo dice, nunca solo el color. */
export function describeUserStatus(user: Pick<ConsultaUser, "active">): { text: string; tone: BadgeTone } {
  return user.active ? { text: "Activo", tone: "ok" } : { text: "Desactivado", tone: "neutral" };
}

/** "2026-11-04T16:02:00Z" como fecha corta en español; "Nunca" sin dato. */
export function formatDateTime(iso: string | null, empty = "Nunca"): string {
  if (!iso) return empty;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return empty;
  return new Intl.DateTimeFormat("es", { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" }).format(date) + " UTC";
}

export function describeConversations(count: number): string {
  if (count === 0) return "Sin conversaciones guardadas";
  return `${count} ${count === 1 ? "conversación" : "conversaciones"}`;
}
