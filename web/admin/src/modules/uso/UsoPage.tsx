import { Button, Loader, Text } from "@mantine/core";
import { useState } from "react";
import { capabilities } from "../../auth/capabilities";
import { useMe } from "../../auth/session";
import { DEFAULT_FILTERS, filtersReady, useUsage, type Granularity, type UsageFilters } from "../../api/usage";
import { Notice } from "../../components/Notice";
import { BalanceCard } from "./BalanceCard";
import { Filters } from "./Filters";
import { KpiRow } from "./KpiRow";
import { QueryLog } from "./QueryLog";
import { ByArtifactTable, ByModelTable } from "./Tables";
import { UsageChart } from "./UsageChart";
import type { GroupBy, Metric } from "./usageUtils";
import "./uso.css";

export function UsoPage() {
  const canSeeBalance = capabilities(useMe()).canSeeBalance;
  const [filters, setFilters] = useState<UsageFilters>(DEFAULT_FILTERS);
  const [metric, setMetric] = useState<Metric>("spend_usd");
  const [groupBy, setGroupBy] = useState<GroupBy>("artifact");
  const [granularity, setGranularity] = useState<Granularity>("day");
  const usage = useUsage(filters, groupBy, granularity, true);

  const data = usage.data;
  return (
    <>
      <h1>Uso</h1>
      <Text c="dimmed">
        Cuánto se usa MIA y cuánto cuesta, por artefacto, modo y modelo. Sale del registro de consultas de MIA, así que incluye
        también las consultas rechazadas, con costo cero.
      </Text>
      <Filters filters={filters} onChange={setFilters} />

      {usage.isError && (
        <Notice tone="danger">
          No se pudo cargar el uso: {usage.error.message}{" "}
          <Button variant="default" size="compact-sm" onClick={() => usage.refetch()}>
            Reintentar
          </Button>
        </Notice>
      )}
      {!filtersReady(filters) && <Text c="dimmed">Elige las fechas del rango para ver el uso.</Text>}
      {usage.isPending && filtersReady(filters) && (
        <Text c="dimmed">
          <Loader size="xs" mr="xs" />
          Cargando el uso...
        </Text>
      )}

      <div className={`uso-stack${usage.isPlaceholderData ? " refreshing" : ""}`}>
        {canSeeBalance && <BalanceCard />}
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
              granularity={granularity}
              onGranularity={setGranularity}
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
