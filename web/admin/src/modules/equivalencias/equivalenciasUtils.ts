import type { Equivalence, EquivalenceInput } from "../../api/types";

// Mismos límites que la API (src/mia/api/routes/equivalences.py). La API es la que hace cumplir las reglas:
// aquí solo se adelanta el mensaje.
export const SIGLA_MIN = 3;
export const SIGLA_MAX = 20;
export const FORM_MIN = 3;
export const FORM_MAX = 120;

/** Minúsculas y sin tildes. */
export function plain(text: string): string {
  return text
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase();
}

/** La sigla como la compara la API: sin tildes, sin puntos ni espacios ("T.F.G." pasa a "tfg"). */
export function normalizeSigla(text: string): string {
  return plain(text).replace(/[^a-z0-9]/g, "");
}

/** La forma desarrollada como la compara la API: palabras en minúsculas, sin tildes, separadas por un espacio. */
export function normalizeForm(text: string): string {
  // Una sigla con puntos ("P.L.N.") cuenta como una sola palabra, igual que en la API.
  const withoutDots = plain(text).replace(/\b[a-z](?:\.[a-z])+\b\.?/g, (match) => match.replaceAll(".", ""));
  return (withoutDots.match(/[a-z0-9]+/g) ?? []).join(" ");
}

/** Si ya existe el mismo par (sin importar mayúsculas, tildes, puntos ni espacios). `ignoreId` es la que se edita. */
export function isDuplicate(input: EquivalenceInput, existing: Equivalence[], ignoreId?: string): Equivalence | null {
  const sigla = normalizeSigla(input.sigla);
  const form = normalizeForm(input.form);
  return existing.find((e) => e.id !== ignoreId && normalizeSigla(e.sigla) === sigla && normalizeForm(e.form) === form) ?? null;
}

/** Mensaje de lo que hay que corregir, o null si está bien. */
export function validateEquivalence(input: EquivalenceInput, existing: Equivalence[], ignoreId?: string): string | null {
  const sigla = input.sigla.trim();
  const form = input.form.trim();
  if (!sigla) return "La sigla no puede estar vacía.";
  if (/[^\p{L}\p{N} .]/u.test(sigla)) return "La sigla solo puede llevar letras y dígitos (se aceptan puntos y espacios).";
  const normalizedSigla = normalizeSigla(sigla);
  if (normalizedSigla.length < SIGLA_MIN || normalizedSigla.length > SIGLA_MAX) {
    return `La sigla debe tener de ${SIGLA_MIN} a ${SIGLA_MAX} caracteres.`;
  }
  if (!form) return "La forma desarrollada no puede estar vacía.";
  const normalizedForm = normalizeForm(form);
  if (normalizedForm.length < FORM_MIN || normalizedForm.length > FORM_MAX) {
    return `La forma desarrollada debe tener de ${FORM_MIN} a ${FORM_MAX} caracteres.`;
  }
  if (!normalizedForm.split(" ").some((word) => word.length >= 3)) {
    return "La forma desarrollada debe llevar al menos una palabra de 3 letras o más.";
  }
  if (normalizedForm === normalizedSigla) return "La forma desarrollada no puede ser igual a la sigla.";
  const duplicate = isDuplicate(input, existing, ignoreId);
  if (duplicate) return `Ya existe la equivalencia «${duplicate.sigla}» = «${duplicate.form}».`;
  return null;
}

/** "Hace 3 días" no hace falta: fecha y hora cortas en el idioma de la persona. */
export function formatWhen(iso: string | null): string {
  if (!iso) return "";
  const date = new Date(iso.endsWith("Z") ? iso : `${iso}Z`);
  return Number.isNaN(date.getTime())
    ? ""
    : date.toLocaleString("es-CR", { dateStyle: "medium", timeStyle: "short" });
}
