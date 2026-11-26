// Eliminación de programas y dominios (feature 023). Contrato en
// specs/023-eliminar-programas-dominios/contracts/eliminar-estructura-api.md.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./client";

export type StructureKind = "unit" | "domain";

export interface DeletionItem {
  kind: string;
  count: number;
  names: string[];
  hint: string;
}

export interface DeletionCheck {
  name: string;
  can_delete: boolean;
  blockers: DeletionItem[];
  affects: DeletionItem[];
}

const path = (kind: StructureKind, id: string) => `/${kind === "unit" ? "units" : "domains"}/${id}`;

/** Qué impide eliminar, o a quién afecta. Se pide cada vez que se abre la ventana: no se guarda. */
export const useDeletionCheck = (kind: StructureKind, id: string) =>
  useQuery({
    queryKey: ["deletion-check", kind, id],
    queryFn: () => apiFetch<DeletionCheck>(`${path(kind, id)}/deletion`),
    gcTime: 0,
    retry: false,
  });

export function useDeleteStructure() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (v: { kind: StructureKind; id: string }) => apiFetch<void>(path(v.kind, v.id), { method: "DELETE" }),
    // Un programa o dominio aparece en el inventario, en el acceso de los artefactos y en los usuarios.
    onSuccess: () =>
      Promise.all(
        ["inventory", "units", "artifacts", "consulta-users"].map((key) => queryClient.invalidateQueries({ queryKey: [key] })),
      ),
  });
}
