import type { ContactFilters } from "../../api/contacts";
import type { ContactStatus } from "../../api/types";
import type { BadgeTone } from "../../components/StatusBadge";

/** Cada estado con su texto y su tono (de la paleta del panel): el texto siempre lo dice, nunca solo el color. */
export const STATUS_LABEL: Record<ContactStatus, { text: string; tone: BadgeTone }> = {
  pendiente: { text: "Pendiente", tone: "neutral" },
  invitada: { text: "Invitada", tone: "info" },
  entrego: { text: "Dejó sus datos", tone: "ok" },
  declino: { text: "No quiso dejar datos", tone: "warn" },
};

export const STATUS_ORDER: ContactStatus[] = ["entrego", "invitada", "pendiente", "declino"];

export const PERSONAL_DATA_NOTE =
  "Son datos personales: el teléfono, el nombre y el correo de quienes escriben al bot. Cada descarga y cada borrado queda registrado (quién, cuándo, cuántos y con qué filtros), sin los datos.";

export const IRREVERSIBLE_NOTE = "Esta acción no se puede deshacer.";

export const NO_FILTER = "todos";
export type EmailFilter = typeof NO_FILTER | "con" | "sin";

/** Lo que eligió la persona en el formulario de filtros. */
export interface FiltersForm {
  botId: string;
  statuses: ContactStatus[];
  email: EmailFilter;
}

export const EMPTY_FORM: FiltersForm = { botId: NO_FILTER, statuses: [], email: NO_FILTER };

/** Del formulario a los filtros de la API (sin los campos que no filtran). */
export function toFilters(form: FiltersForm): ContactFilters {
  const filters: ContactFilters = { status: [...form.statuses] };
  if (form.botId !== NO_FILTER) filters.bot_id = form.botId;
  if (form.email === "con") filters.has_email = true;
  if (form.email === "sin") filters.has_email = false;
  return filters;
}

export function hasFilters(form: FiltersForm): boolean {
  return form.botId !== NO_FILTER || form.statuses.length > 0 || form.email !== NO_FILTER;
}

/** "contacto" o "contactos" según el conteo. */
function contactos(count: number): string {
  return count === 1 ? "1 contacto" : `${count} contactos`;
}

/** El título de la ventana de confirmación del borrado masivo, con el conteo. */
export function bulkTitle(count: number): string {
  return `Borrar ${contactos(count)}`;
}

/** El texto de la ventana de confirmación del borrado masivo: dice cuántos se borran y que no se puede deshacer. */
export function bulkText(count: number, filtered: boolean): string {
  const alcance = filtered ? "los contactos que cumplen los filtros" : "todos los contactos";
  return `Se borrarán ${contactos(count)} (${alcance}), con su teléfono, nombre y correo. ${IRREVERSIBLE_NOTE}`;
}

/** Un teléfono de Costa Rica como "+506 8888-7777"; cualquier otro se deja como llegó. */
export function formatPhone(phone: string): string {
  const match = /^\+506(\d{4})(\d{4})$/.exec(phone);
  return match ? `+506 ${match[1]}-${match[2]}` : phone;
}

/** La fecha ISO como "12/11/2026, 3:04 p. m." (hora local); si no se puede leer, el texto tal cual. */
export function formatDate(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString("es-CR", { dateStyle: "short", timeStyle: "short" });
}

/** Cuántas páginas hay para un total. */
export function pageCount(total: number, pageSize: number): number {
  return Math.max(1, Math.ceil(total / pageSize));
}
