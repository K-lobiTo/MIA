import { apiFetch } from "./client";
import type { Me } from "./types";

export function fetchMe(): Promise<Me> {
  return apiFetch<Me>("/me");
}
