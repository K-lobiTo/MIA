import { useState } from "react";
import { useOutletContext } from "react-router-dom";
import { useAdminKey } from "../../api/client";
import { DEFAULT_FILTERS, filtersReady, useUsage, type UsageFilters } from "../../api/usage";
import { BalanceCard } from "./BalanceCard";
import { Filters } from "./Filters";
import { KpiRow } from "./KpiRow";
import { QueryLog } from "./QueryLog";
import { ByArtifactTable, ByModelTable } from "./Tables";
import { UsageChart } from "./UsageChart";
import type { GroupBy, Metric } from "./usageUtils";
import "./uso.css";

export function UsoPage() {
  const adminKey = useAdminKey();
  const { askForKey } = useOutletContext<{ askForKey: () => void }>();
  const [filters, setFilters] = useState<UsageFilters>(DEFAULT_FILTERS);
  const [metric, setMetric] = useState<Metric>("spend_usd");
  const [groupBy, setGroupBy] = useState<GroupBy>("artifact");
  const usage = useUsage(filters, groupBy, Boolean(adminKey));

  if (!adminKey) {
    return (
      <>
        <h1>Uso</h1>
        <div className="notice notice-admin">
          Este módulo necesita la clave de administración.{" "}
          <button className="btn btn-small btn-primary" onClick={askForKey}>
            Ingresar clave
          </button>
        </div>
      </>
    );
  }

  const data = usage.data;
  return (
    <>
      <h1>Uso</h1>
      <p className="muted">
        Cuánto se usa MIA y cuánto cuesta, por artefacto, modo y modelo. Sale del registro de consultas de MIA, así que incluye
        también las consultas rechazadas, con costo cero.
      </p>
      <Filters filters={filters} onChange={setFilters} />

      {usage.isError && (
        <div className="notice notice-danger" role="alert">
          No se pudo cargar el uso: {usage.error.message}{" "}
          <button className="btn btn-small" onClick={() => usage.refetch()}>
            Reintentar
          </button>
        </div>
      )}
      {!filtersReady(filters) && <p className="muted">Elige las fechas del rango para ver el uso.</p>}
      {usage.isPending && filtersReady(filters) && <p className="muted">Cargando el uso...</p>}

      <div className={`uso-stack${usage.isPlaceholderData ? " refreshing" : ""}`}>
        <BalanceCard />
        {data && (
          <>
            <KpiRow kpis={data.kpis} />
            <UsageChart
              series={data.series}
              bucket={data.period.bucket}
              metric={metric}
              groupBy={groupBy}
              onMetric={setMetric}
              onGroupBy={setGroupBy}
            />
            <ByArtifactTable rows={data.by_artifact} />
            <ByModelTable rows={data.by_model} />
          </>
        )}
        <QueryLog filters={filters} />
      </div>
    </>
  );
}
