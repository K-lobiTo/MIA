import type { BulkDeleteResponse, DocumentItem, DomainNode, FolderNode, Inventory } from "../../api/types";

/** Un documento que se va a eliminar. `DocumentItem` no trae el dominio, así que se arma con el contexto del árbol. */
export interface DocumentoAEliminar {
  id: string;
  filename: string;
  status: DocumentItem["status"];
  image_count: number;
  domain_id: string;
  domain_name: string;
}

export function aEliminar(document: DocumentItem, domainId: string, domainName: string): DocumentoAEliminar {
  return {
    id: document.id,
    filename: document.filename,
    status: document.status,
    image_count: document.image_count,
    domain_id: domainId,
    domain_name: domainName,
  };
}

/** Todos los documentos del inventario por id, con el dominio al que pertenecen. */
export function documentosDelInventario(inventory: Inventory): Map<string, DocumentoAEliminar> {
  const documentos = new Map<string, DocumentoAEliminar>();
  const recorrer = (nodo: { documents: DocumentItem[]; folders: FolderNode[] }, domain: DomainNode) => {
    for (const d of nodo.documents) documentos.set(d.id, aEliminar(d, domain.id, domain.name));
    for (const carpeta of nodo.folders) recorrer(carpeta, domain);
  };
  for (const domain of [...inventory.units.flatMap((u) => u.domains), ...inventory.unassigned_domains]) recorrer(domain, domain);
  return documentos;
}

// --- Selección ---------------------------------------------------------------------------------------------------

/** Agrega el documento si no estaba y lo quita si estaba (sin modificar el conjunto recibido). */
export function alternar(selected: ReadonlySet<string>, id: string): Set<string> {
  const next = new Set(selected);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  return next;
}

/** Marca todos los ids, o los desmarca todos si ya estaban todos marcados (casilla de una carpeta o dominio). */
export function marcarGrupo(selected: ReadonlySet<string>, ids: readonly string[]): Set<string> {
  const next = new Set(selected);
  const todos = ids.length > 0 && ids.every((id) => next.has(id));
  for (const id of ids) {
    if (todos) next.delete(id);
    else next.add(id);
  }
  return next;
}

export function estadoDeGrupo(selected: ReadonlySet<string>, ids: readonly string[]): "ninguno" | "algunos" | "todos" {
  const marcados = ids.filter((id) => selected.has(id)).length;
  if (marcados === 0) return "ninguno";
  return marcados === ids.length ? "todos" : "algunos";
}

/** Quita de la selección los documentos que ya no están (eliminados o fuera del inventario). */
export function sinEliminados(selected: ReadonlySet<string>, eliminados: readonly string[]): Set<string> {
  const quitar = new Set(eliminados);
  return new Set([...selected].filter((id) => !quitar.has(id)));
}

// --- Textos de la confirmación ------------------------------------------------------------------------------------

export const MAX_NOMBRES = 10;

/** Los primeros nombres y, si hay más, `y N más`. */
export function recortarNombres<T>(items: readonly T[], max = MAX_NOMBRES): { visibles: T[]; resto: number } {
  return { visibles: items.slice(0, max), resto: Math.max(0, items.length - max) };
}

export const textoDeResto = (resto: number) => `y ${resto} más`;

export function sumarImagenes(documentos: readonly { image_count: number }[]): number {
  return documentos.reduce((total, d) => total + d.image_count, 0);
}

export const tituloConfirmacion = (cantidad: number) => (cantidad === 1 ? "Eliminar documento" : `Eliminar ${cantidad} documentos`);

export const textoBoton = (cantidad: number) => (cantidad === 1 ? "Eliminar" : `Eliminar ${cantidad} documentos`);

export function textoImagenes(cantidad: number): string | null {
  if (cantidad <= 0) return null;
  return cantidad === 1 ? "Se pierde también 1 imagen asociada." : `Se pierden también ${cantidad} imágenes asociadas.`;
}

/** Un documento en cola o procesándose: eliminarlo cancela su procesamiento. */
export function hayEnProceso(documentos: readonly { status: string }[]): boolean {
  return documentos.some((d) => d.status === "pending" || d.status === "processing");
}

export const AVISO_PERDIDA =
  "Se pierden el documento, sus imágenes asociadas y su contenido en las respuestas de todos los artefactos, incluido el bot de WhatsApp.";
export const AVISO_IRREVERSIBLE =
  "No se puede deshacer. Para recuperarlo hay que volver a subir el archivo original y asociar de nuevo sus imágenes.";
export const AVISO_EN_PROCESO = "Se cancelará su procesamiento.";

// --- Resultado ---------------------------------------------------------------------------------------------------

export type Motivo = "out_of_scope" | "busy" | "error" | "otro";

const MENSAJE_DE_MOTIVO: Record<Exclude<Motivo, "otro">, string> = {
  out_of_scope: "Está fuera de tus programas.",
  busy: "Se está procesando, intenta de nuevo en un momento.",
  error: "No se pudo quitar del almacén de búsqueda; sigue como estaba.",
};

export function mensajeDeMotivo(motivo: Motivo, detalle?: string): string {
  return motivo === "otro" ? detalle || "No se pudo eliminar." : MENSAJE_DE_MOTIVO[motivo];
}

export interface Fallo {
  documento: DocumentoAEliminar;
  motivo: Motivo;
  mensaje: string;
}

export interface Resultado {
  eliminados: DocumentoAEliminar[];
  /** Ya no existían (otra persona los eliminó antes): cuentan como eliminados. */
  yaNoExistian: DocumentoAEliminar[];
  fallidos: Fallo[];
}

/** Lo que `ejecutar` necesita de la API: una función por documento y otra de lote. */
export interface Eliminador {
  uno: (documento: DocumentoAEliminar) => Promise<void>;
  lote: (ids: string[]) => Promise<BulkDeleteResponse>;
}

function motivoDeEstado(status: number): Motivo {
  if (status === 403) return "out_of_scope";
  if (status === 409) return "busy";
  if (status === 503) return "error";
  return "otro";
}

/** Elimina los documentos (uno o varios) y ordena el resultado: eliminados, los que ya no existían y los fallidos. Un
 * 404 o `not_found` no es un fallo: el documento ya no está, que es lo que se quería. */
export async function ejecutar(documentos: readonly DocumentoAEliminar[], api: Eliminador): Promise<Resultado> {
  const resultado: Resultado = { eliminados: [], yaNoExistian: [], fallidos: [] };

  if (documentos.length === 1) {
    const [documento] = documentos;
    try {
      await api.uno(documento);
      resultado.eliminados.push(documento);
    } catch (caught) {
      const error = caught as { status?: number; message?: string };
      if (error.status === 404) resultado.yaNoExistian.push(documento);
      else {
        const motivo = motivoDeEstado(error.status ?? 0);
        resultado.fallidos.push({ documento, motivo, mensaje: mensajeDeMotivo(motivo, error.message) });
      }
    }
    return resultado;
  }

  const porId = new Map(documentos.map((d) => [d.id, d]));
  const respuesta = await api.lote(documentos.map((d) => d.id));
  for (const item of respuesta.results) {
    const documento = porId.get(item.document_id);
    if (!documento) continue;
    if (item.status === "deleted") resultado.eliminados.push(documento);
    else if (item.status === "not_found") resultado.yaNoExistian.push(documento);
    else {
      const motivo: Motivo = item.status;
      resultado.fallidos.push({ documento, motivo, mensaje: mensajeDeMotivo(motivo, item.detail) });
    }
  }
  return resultado;
}

/** El aviso de lo que se logró: `Documento eliminado`, `3 documentos eliminados`, con la nota de los que ya no existían. */
export function avisoFinal(resultado: Resultado): string {
  const total = resultado.eliminados.length + resultado.yaNoExistian.length;
  const base = total === 1 ? "Documento eliminado" : `${total} documentos eliminados`;
  const n = resultado.yaNoExistian.length;
  if (n === 0) return base;
  return `${base} (${n === 1 ? "1 ya no existía" : `${n} ya no existían`}).`;
}

/** Ids que ya no están en el inventario tras la operación (eliminados y los que ya no existían). */
export function idsRetirados(resultado: Resultado): string[] {
  return [...resultado.eliminados, ...resultado.yaNoExistian].map((d) => d.id);
}

// --- Estado de la ventana de eliminación -------------------------------------------------------------------------

/** Lo que la ventana tiene en cada momento: qué falta eliminar, qué falló la última vez y el error de la petición. */
export interface Sesion {
  pendientes: readonly DocumentoAEliminar[];
  fallidos: readonly Fallo[];
  error: string | null;
}

export const sesionInicial = (documentos: readonly DocumentoAEliminar[]): Sesion => ({
  pendientes: documentos,
  fallidos: [],
  error: null,
});

/** El botón de confirmar dice `Reintentar` después de un fallo o de un error de la petición. */
export function etiquetaDeConfirmar(sesion: Sesion): string {
  return sesion.fallidos.length > 0 || sesion.error !== null ? "Reintentar" : textoBoton(sesion.pendientes.length);
}

export interface Avance {
  sesion: Sesion;
  /** El resultado del intento, o null si la petición completa falló (nada se da por eliminado). */
  resultado: Resultado | null;
  /** No queda nada por eliminar: la ventana se cierra. */
  terminado: boolean;
}

/** Confirma sobre lo pendiente. Con fallos parciales queda pendiente solo lo fallido, así el reintento reenvía únicamente
 * esos (con uno solo usa la ruta por documento, con varios la de lote). Es lo único que llama al eliminador: cancelar o
 * cerrar la ventana no pasa por aquí. */
export async function confirmar(sesion: Sesion, api: Eliminador): Promise<Avance> {
  try {
    const resultado = await ejecutar(sesion.pendientes, api);
    if (resultado.fallidos.length === 0) return { sesion: { pendientes: [], fallidos: [], error: null }, resultado, terminado: true };
    return {
      sesion: { pendientes: resultado.fallidos.map((f) => f.documento), fallidos: resultado.fallidos, error: null },
      resultado,
      terminado: false,
    };
  } catch (caught) {
    const mensaje = caught instanceof Error ? caught.message : "No se pudo eliminar.";
    return { sesion: { ...sesion, error: mensaje }, resultado: null, terminado: false };
  }
}
