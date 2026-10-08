import { useArtifacts } from "../../api/artifacts";
import type { ModeId } from "../../api/types";
import { filtersReady, type PeriodName, type UsageFilters } from "../../api/usage";

const PERIODS: Record<PeriodName, string> = { today: "Hoy", "7d": "7 días", "30d": "30 días", custom: "Rango" };

interface Props {
  filters: UsageFilters;
  onChange: (filters: UsageFilters) => void;
}

/** Filtros que controlan todo el módulo: período, artefacto y modo (USO-1). */
export function Filters({ filters, onChange }: Props) {
  const artifacts = useArtifacts(true);
  const set = (changes: Partial<UsageFilters>) => onChange({ ...filters, ...changes });

  return (
    <div className="filters" role="search" aria-label="Filtros del uso">
      <div className="segmented" role="group" aria-label="Período">
        {(Object.keys(PERIODS) as PeriodName[]).map((period) => (
          <button key={period} type="button" aria-pressed={filters.period === period} onClick={() => set({ period })}>
            {PERIODS[period]}
          </button>
        ))}
      </div>
      {filters.period === "custom" && (
        <div className="date-range">
          <label>
            Desde
            <input type="date" value={filters.from} max={filters.to || undefined} onChange={(e) => set({ from: e.target.value })} />
          </label>
          <label>
            Hasta
            <input type="date" value={filters.to} min={filters.from || undefined} onChange={(e) => set({ to: e.target.value })} />
          </label>
          {!filtersReady(filters) && <span className="hint">Elige las dos fechas (la inicial no puede ser posterior a la final).</span>}
        </div>
      )}
      <label className="select-label">
        Artefacto
        <select value={filters.artifactId} onChange={(e) => set({ artifactId: e.target.value })}>
          <option value="">Todos</option>
          {artifacts.data?.artifacts.map((artifact) => (
            <option key={artifact.id} value={artifact.id}>
              {artifact.name}
            </option>
          ))}
        </select>
      </label>
      <label className="select-label">
        Modo
        <select value={filters.mode} onChange={(e) => set({ mode: e.target.value as "" | ModeId })}>
          <option value="">Todos</option>
          <option value="literal">Literal</option>
          <option value="razonamiento">Con razonamiento</option>
        </select>
      </label>
    </div>
  );
}
