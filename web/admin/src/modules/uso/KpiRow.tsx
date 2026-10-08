import type { UsageResponse } from "../../api/types";
import { describeDelta, formatLatency, formatMetric, formatTokens, formatUsd, type DeltaTone } from "./usageUtils";

interface TileProps {
  label: string;
  value: string;
  detail?: string;
  change: number | null | undefined;
  unit: "%" | "pts";
  // Si subir es bueno (true), malo (false) o neutro (null): decide el color de la variación.
  upIsGood: boolean | null;
}

const TONE_CLASS: Record<DeltaTone, string> = { good: "delta-good", bad: "delta-bad", neutral: "delta-neutral" };

function Tile({ label, value, detail, change, unit, upIsGood }: TileProps) {
  const delta = describeDelta(change, unit, upIsGood);
  return (
    <div className="kpi">
      <span className="kpi-label">{label}</span>
      <span className="kpi-value">{value}</span>
      {detail && <span className="kpi-detail">{detail}</span>}
      <span className={`kpi-delta ${delta ? TONE_CLASS[delta.tone] : "delta-neutral"}`}>
        {delta ? (
          <>
            <span aria-hidden="true">{delta.arrow}</span> {delta.text} <span className="sr-only">frente al período anterior</span>
          </>
        ) : (
          "Sin período anterior con qué comparar"
        )}
      </span>
    </div>
  );
}

/** Indicadores del período, cada uno con su variación frente al período anterior de igual duración (USO-2). */
export function KpiRow({ kpis }: { kpis: UsageResponse["kpis"] }) {
  const latency = kpis.latency_ms;
  return (
    <section className="kpis" aria-label="Indicadores del período">
      <Tile label="Gasto" value={formatUsd(kpis.spend_usd.value)} change={kpis.spend_usd.change_pct} unit="%" upIsGood={false} />
      <Tile label="Consultas" value={formatMetric("queries", kpis.queries.value)} change={kpis.queries.change_pct} unit="%" upIsGood={null} />
      <Tile
        label="Tokens"
        value={formatTokens(kpis.tokens.value)}
        detail={`entrada ${formatTokens(kpis.tokens.input)} · salida ${formatTokens(kpis.tokens.output)} · razonamiento ${formatTokens(kpis.tokens.reasoning)}`}
        change={kpis.tokens.change_pct}
        unit="%"
        upIsGood={null}
      />
      <Tile label="Costo medio por consulta" value={formatUsd(kpis.avg_cost_usd.value)} change={kpis.avg_cost_usd.change_pct} unit="%" upIsGood={false} />
      <Tile
        label="Tiempo de respuesta (mediana)"
        value={formatLatency(latency.p50)}
        detail={`el 95 % tarda hasta ${formatLatency(latency.p95)}`}
        change={latency.change_pct}
        unit="%"
        upIsGood={false}
      />
      <Tile label="Sin información" value={`${kpis.no_info_pct.value} %`} change={kpis.no_info_pct.change_pts} unit="pts" upIsGood={false} />
      <Tile label="Errores" value={`${kpis.error_pct.value} %`} change={kpis.error_pct.change_pts} unit="pts" upIsGood={false} />
      <Tile
        label="Respuestas útiles"
        value={kpis.useful_pct.rated > 0 ? `${kpis.useful_pct.value} %` : "sin calificar"}
        detail={`${kpis.useful_pct.rated} ${kpis.useful_pct.rated === 1 ? "calificada" : "calificadas"}`}
        change={kpis.useful_pct.change_pts}
        unit="pts"
        upIsGood={true}
      />
    </section>
  );
}
