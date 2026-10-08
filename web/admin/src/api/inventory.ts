import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "./client";
import type { Inventory, Unit } from "./types";

export function useInventory(refetchInterval?: number | false) {
  return useQuery({
    queryKey: ["inventory"],
    queryFn: () => apiFetch<Inventory>("/inventory"),
    refetchInterval,
  });
}

export function useUnits() {
  return useQuery({ queryKey: ["units"], queryFn: () => apiFetch<Unit[]>("/units") });
}
