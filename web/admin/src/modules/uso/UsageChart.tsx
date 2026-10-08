import { useMemo, useState } from "react";
import { assignColors } from "./colors";
import { GROUP_LABEL, METRIC_LABEL, bucketLabel, buildChartData, formatAxis, formatMetric, niceTicks, type GroupBy, type Metric } from "./usageUtils";
import type { UsageResponse } from "../../api/types";

// Geometría fija del lienzo; el SVG se escala con su contenedor (viewBox).
const W = 860;
const H = 300;
const MARGIN = { top: 12, right: 12, bottom: 30, left: 52 };
const MAX_BAR = 24; // las barras nunca llenan su espacio: el aire es parte del diseño
const GAP = 2; // separación entre segmentos apilados, en el color de la superficie
const RADIUS = 4; // extremo redondeado de los datos; el lado de la base queda recto

interface Props {
  series: UsageResponse["series"];
  bucket: "hour" | "day";
  metric: Metric;
  groupBy: GroupBy;
  onMetric: (metric: Metric) => void;
  onGroupBy: (groupBy: GroupBy) => void;
}

function Segmented<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: Record<T, string>;
  onChange: (value: T) => void;
}) {
  return (
    <div className="segmented" role="group" aria-label={label}>
      {(Object.keys(options) as T[]).map((key) => (
        <button key={key} type="button" aria-pressed={value === key} onClick={() => onChange(key)}>
          {options[key]}
        </button>
      ))}
    </div>
  );
}

/** Barra con el extremo superior redondeado y la base recta. */
function topRoundedBar(x: number, y: number, w: number, h: number): string {
  const r = Math.min(RADIUS, w / 2, h);
  return `M${x},${y + h}V${y + r}A${r},${r} 0 0 1 ${x + r},${y}H${x + w - r}A${r},${r} 0 0 1 ${x + w},${y + r}V${y + h}Z`;
}

export function UsageChart({ series, bucket, metric, groupBy, onMetric, onGroupBy }: Props) {
  const data = useMemo(() => buildChartData(series, metric), [series, metric]);
  const colors = useMemo(() => assignColors(data.names), [data.names]);
  const [hover, setHover] = useState<number | null>(null);
  const [asTable, setAsTable] = useState(false);

  const ticks = niceTicks(data.max);
  const top = ticks[ticks.length - 1];
  const plotW = W - MARGIN.left - MARGIN.right;
  const plotH = H - MARGIN.top - MARGIN.bottom;
  const n = Math.max(1, data.buckets.length);
  const slot = plotW / n;
  const barW = Math.min(MAX_BAR, slot * 0.7);
  const yOf = (value: number) => MARGIN.top + plotH - (top > 0 ? (value / top) * plotH : 0);
  const labelEvery = Math.ceil(n / 8);
  const legendTotals = data.names.map((_, j) => data.values.reduce((sum, row) => sum + row[j], 0));
  const empty = data.max === 0;
  const hovered = hover !== null ? hover : null;

  return (
    <section className="card chart-card" aria-label="Uso a lo largo del tiempo">
      <div className="chart-head">
        <h2>
          {METRIC_LABEL[metric]} por {bucket === "hour" ? "hora" : "día"}
          {metric === "spend_usd" && <span className="muted"> (USD)</span>}
        </h2>
        <div className="chart-controls">
          <Segmented label="Métrica" value={metric} options={METRIC_LABEL} onChange={onMetric} />
          <Segmented label="Desglose" value={groupBy} options={GROUP_LABEL} onChange={onGroupBy} />
          <button className="btn btn-small" onClick={() => setAsTable(!asTable)}>
            {asTable ? "Ver gráfica" : "Ver como tabla"}
          </button>
        </div>
      </div>

      {data.names.length >= 2 && (
        <ul className="legend" aria-label="Leyenda">
          {data.names.map((name, j) => (
            <li key={name}>
              <span className="swatch" style={{ background: colors[name] }} aria-hidden="true" />
              <span>{name}</span>
              <span className="muted">{formatMetric(metric, legendTotals[j])}</span>
            </li>
          ))}
        </ul>
      )}

      {empty && <p className="muted chart-empty">No hay consultas en este período con los filtros elegidos.</p>}

      {!empty && asTable && (
        <div className="table-wrap">
          <table>
            <caption className="sr-only">
              {METRIC_LABEL[metric]} por {bucket === "hour" ? "hora" : "día"}, desglosado por {GROUP_LABEL[groupBy].toLowerCase()}
            </caption>
            <thead>
              <tr>
                <th scope="col">{bucket === "hour" ? "Hora" : "Día"}</th>
                {data.names.map((name) => (
                  <th scope="col" key={name} className="num">
                    {name}
                  </th>
                ))}
                {data.names.length > 1 && <th scope="col" className="num">Total</th>}
              </tr>
            </thead>
            <tbody>
              {data.buckets.map((b, i) => (
                <tr key={b}>
                  <th scope="row">{bucketLabel(b, bucket)}</th>
                  {data.values[i].map((value, j) => (
                    <td key={data.names[j]} className="num">
                      {value > 0 ? formatMetric(metric, value) : "-"}
                    </td>
                  ))}
                  {data.names.length > 1 && <td className="num">{formatMetric(metric, data.totals[i])}</td>}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!empty && !asTable && (
        <div className="chart-wrap" onMouseLeave={() => setHover(null)}>
          <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${METRIC_LABEL[metric]} por ${bucket === "hour" ? "hora" : "día"}`}>
            {ticks.map((tick) => (
              <g key={tick}>
                <line x1={MARGIN.left} x2={W - MARGIN.right} y1={yOf(tick)} y2={yOf(tick)} className="grid" />
                <text x={MARGIN.left - 8} y={yOf(tick) + 4} textAnchor="end" className="axis-label">
                  {formatAxis(metric, tick)}
                </text>
              </g>
            ))}

            {data.buckets.map((b, i) => {
              const cx = MARGIN.left + slot * (i + 0.5);
              const x = cx - barW / 2;
              let acc = 0;
              const segments = data.values[i]
                .map((value, j) => ({ value, j }))
                .filter((s) => s.value > 0);
              return (
                <g key={b}>
                  {hovered === i && (
                    <rect x={MARGIN.left + slot * i} y={MARGIN.top} width={slot} height={plotH} className="hover-band" />
                  )}
                  {segments.map((segment, k) => {
                    const yBottom = yOf(acc);
                    acc += segment.value;
                    const yTop = yOf(acc);
                    const isTop = k === segments.length - 1;
                    // Cada segmento deja 2 px de aire arriba (salvo el último): separa sin dibujar bordes.
                    const height = Math.max(1, yBottom - yTop - (isTop ? 0 : GAP));
                    const color = colors[data.names[segment.j]];
                    return isTop ? (
                      <path key={segment.j} d={topRoundedBar(x, yBottom - height, barW, height)} fill={color} />
                    ) : (
                      <rect key={segment.j} x={x} y={yBottom - height} width={barW} height={height} fill={color} />
                    );
                  })}
                  {i % labelEvery === 0 && (
                    <text x={cx} y={H - 8} textAnchor="middle" className="axis-label">
                      {bucketLabel(b, bucket)}
                    </text>
                  )}
                  {/* Zona de interacción más grande que la barra: el ratón o el teclado no tienen que acertarle. */}
                  <rect
                    x={MARGIN.left + slot * i}
                    y={MARGIN.top}
                    width={slot}
                    height={plotH}
                    fill="transparent"
                    tabIndex={data.totals[i] > 0 ? 0 : -1}
                    aria-label={`${bucketLabel(b, bucket)}: ${formatMetric(metric, data.totals[i])}`}
                    onMouseEnter={() => setHover(i)}
                    onFocus={() => setHover(i)}
                    onBlur={() => setHover(null)}
                  />
                </g>
              );
            })}
            <line x1={MARGIN.left} x2={W - MARGIN.right} y1={yOf(0)} y2={yOf(0)} className="baseline" />
          </svg>

          {hovered !== null && data.totals[hovered] > 0 && (
            <div
              className="chart-tooltip"
              role="status"
              style={{
                left: `${((MARGIN.left + slot * (hovered + 0.5)) / W) * 100}%`,
                transform: hovered > n / 2 ? "translateX(-105%)" : "translateX(5%)",
              }}
            >
              <strong>{bucket === "hour" ? `${bucketLabel(data.buckets[hovered], bucket)} h` : data.buckets[hovered]}</strong>
              <span className="muted"> · {formatMetric(metric, data.totals[hovered])}</span>
              <ul>
                {data.names
                  .map((name, j) => ({ name, value: data.values[hovered][j] }))
                  .filter((entry) => entry.value > 0)
                  .reverse()
                  .map((entry) => (
                    <li key={entry.name}>
                      <span className="swatch" style={{ background: colors[entry.name] }} aria-hidden="true" />
                      {entry.name}: {formatMetric(metric, entry.value)}
                    </li>
                  ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
