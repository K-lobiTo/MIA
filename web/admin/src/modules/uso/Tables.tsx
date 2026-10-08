import { Link } from "react-router-dom";
import type { UsageResponse } from "../../api/types";
import { Meter } from "../artefactos/Meter";
import { formatLatency, formatMetric, formatUsd } from "./usageUtils";

/** Gasto por artefacto, con el gasto de hoy frente a su tope y un acceso a su configuración (USO-4). */
export function ByArtifactTable({ rows }: { rows: UsageResponse["by_artifact"] }) {
  return (
    <section className="card" aria-label="Por artefacto">
      <h2>Por artefacto</h2>
      {rows.length === 0 ? (
        <p className="muted">No hay artefactos registrados.</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">Artefacto</th>
                <th scope="col">Hoy frente a su tope</th>
                <th scope="col" className="num">Gasto</th>
                <th scope="col" className="num">Consultas</th>
                <th scope="col" className="num">Tiempo medio</th>
                <th scope="col"><span className="sr-only">Configuración</span></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <th scope="row">{row.name}</th>
                  <td>
                    <Meter label="Gasto de hoy" spent={row.today_spent_usd} cap={row.daily_cap_usd} />
                  </td>
                  <td className="num">{formatUsd(row.spend_usd)}</td>
                  <td className="num">{formatMetric("queries", row.queries)}</td>
                  <td className="num">{formatLatency(row.avg_latency_ms)}</td>
                  <td>
                    <Link to="/artefactos" className="btn btn-small">
                      Configurar
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

/** Qué modelo concentra el gasto: sirve para comparar modelos al cambiar el de un modo (USO-5). */
export function ByModelTable({ rows }: { rows: UsageResponse["by_model"] }) {
  return (
    <section className="card" aria-label="Por modelo">
      <h2>Por modelo</h2>
      {rows.length === 0 ? (
        <p className="muted">Ninguna consulta llegó a un modelo en este período.</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">Modelo</th>
                <th scope="col" className="num">Consultas</th>
                <th scope="col" className="num">Tokens</th>
                <th scope="col" className="num">Gasto</th>
                <th scope="col" className="num">Tiempo medio</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.model}>
                  <th scope="row" className="mono">{row.model}</th>
                  <td className="num">{formatMetric("queries", row.queries)}</td>
                  <td className="num">{formatMetric("tokens", row.tokens)}</td>
                  <td className="num">{formatUsd(row.spend_usd)}</td>
                  <td className="num">{formatLatency(row.avg_latency_ms)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
