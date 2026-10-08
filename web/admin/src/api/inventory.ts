import { useQuery } from "@tanstack/react-query";
import { hasPendingDocuments } from "../modules/inventario/inventoryUtils";
import { apiFetch } from "./client";
import type { Inventory, Unit } from "./types";

// Mientras haya documentos en cola o procesando se vuelve a consultar cada 5 s, sin recargar la
// página, y se deja de hacer cuando todos quedan listos o en error (INV-5).
const POLL_MS = 5000;

export function useInventory() {
  return useQuery({
    queryKey: ["inventory"],
    queryFn: () => apiFetch<Inventory>("/inventory"),
    refetchInterval: (query) => (hasPendingDocuments(query.state.data) ? POLL_MS : false),
  });
}

export function useUnits() {
  return useQuery({ queryKey: ["units"], queryFn: () => apiFetch<Unit[]>("/units") });
}
