import { useState } from "react";
import { downloadCsv, useQueryDetail, useQueryLog, type UsageFilters } from "../../api/usage";
import type { Outcome } from "../../api/types";
import { ApiError } from "../../api/client";
import { OUTCOME_LABEL, formatLatency, formatTokens, formatUsd } from "./usageUtils";

const RATING_LABEL = { util: "Útil", no_util: "No útil" } as const;

function formatDate(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString("es-CR", { dateStyle: "short", timeStyle: "short" });
}

function Detail({ id, onClose }: { id: string; onClose: () => void }) {
  const detail = useQueryDetail(id);
  const data = detail.data;
  return (
    <div className="overlay" role="dialog" aria-modal="true" aria-label="Detalle de la consulta">
      <div className="dialog dialog-wide">
        <h2>Detalle de la consulta</h2>
        {detail.isPending && <p className="muted">Cargando...</p>}
        {detail.isError && <div className="notice notice-danger" role="alert">{detail.error.message}</div>}
        {data && (
          <dl className="detail">
            <dt>Pregunta</dt>
            <dd className="question">{data.question || <span className="muted">(vacía)</span>}</dd>
            <dt>Artefacto</dt>
            <dd>{data.artifact ?? "(ninguno)"} · modo {data.mode}</dd>
            <dt>Resultado</dt>
            <dd>
              <span className={OUTCOME_LABEL[data.outcome].className}>{OUTCOME_LABEL[data.outcome].text}</span>
              {data.reject_reason && <span className="muted"> {data.reject_reason}</span>}
            </dd>
            <dt>Dominios consultados</dt>
            <dd>{data.domains.length > 0 ? data.domains.join(", ") : <span className="muted">(ninguno)</span>}</dd>
            <dt>Documentos citados</dt>
            <dd>
              {data.sources.length > 0 ? (
                <ul>
                  {data.sources.map((source) => (
                    <li key={`${source.domain}/${source.document}`}>
                      {source.document} <span className="muted">({source.domain})</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <span className="muted">(ninguno)</span>
              )}
            </dd>
            <dt>Modelo y costo</dt>
            <dd>
              {data.model ?? "(no llegó al modelo)"} · {formatUsd(data.cost_usd)}
              {data.cost_estimated && " (estimado)"} · {formatLatency(data.latency_ms)}
            </dd>
            <dt>Calificación</dt>
            <dd>
              {data.rating ? RATING_LABEL[data.rating] : <span className="muted">sin calificar</span>}
              {data.rating_comment && <> · "{data.rating_comment}"</>}
            </dd>
          </dl>
        )}
        <div className="dialog-actions">
          <button className="btn btn-primary" onClick={onClose}>
            Cerrar
          </button>
        </div>
      </div>
    </div>
  );
}

/** Registro de consultas del período: de la más reciente a la más antigua, con su detalle y su descarga en CSV (USO-6, USO-8). */
export function QueryLog({ filters }: { filters: UsageFilters }) {
  const [page, setPage] = useState(1);
  const [outcome, setOutcome] = useState<"" | Outcome>("");
  const [open, setOpen] = useState<string | null>(null);
  const [withQuestions, setWithQuestions] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const log = useQueryLog(filters, page, outcome);
  const data = log.data;
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  async function download() {
    setDownloadError(null);
    try {
      await downloadCsv(filters, withQuestions);
    } catch (caught) {
      setDownloadError(caught instanceof ApiError ? caught.message : "No se pudo descargar el archivo.");
    }
  }

  return (
    <section className="card" aria-label="Registro de consultas">
      <div className="chart-head">
        <h2>Registro de consultas</h2>
        <div className="chart-controls">
          <label className="select-label">
            Resultado
            <select
              value={outcome}
              onChange={(e) => {
                setOutcome(e.target.value as "" | Outcome);
                setPage(1);
              }}
            >
              <option value="">Todos</option>
              {(Object.keys(OUTCOME_LABEL) as Outcome[]).map((key) => (
                <option key={key} value={key}>
                  {OUTCOME_LABEL[key].text}
                </option>
              ))}
            </select>
          </label>
          <label className="choice-inline" title="Las preguntas pueden contener datos personales">
            <input type="checkbox" checked={withQuestions} onChange={(e) => setWithQuestions(e.target.checked)} />
            Incluir las preguntas
          </label>
          <button className="btn btn-small" onClick={() => void download()}>
            Descargar CSV
          </button>
        </div>
      </div>
      {downloadError && <div className="notice notice-danger" role="alert">{downloadError}</div>}

      {log.isPending && <p className="muted">Cargando el registro...</p>}
      {log.isError && <div className="notice notice-danger" role="alert">{log.error.message}</div>}
      {data && data.items.length === 0 && <p className="muted">No hay consultas con estos filtros.</p>}
      {data && data.items.length > 0 && (
        <>
          <div className="table-wrap">
            <table className="log-table">
              <thead>
                <tr>
                  <th scope="col">Fecha</th>
                  <th scope="col">Artefacto</th>
                  <th scope="col">Modo</th>
                  <th scope="col">Modelo</th>
                  <th scope="col" className="num">Tokens</th>
                  <th scope="col" className="num">Costo</th>
                  <th scope="col" className="num">Tiempo</th>
                  <th scope="col">Resultado</th>
                  <th scope="col">Calificación</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <button className="btn-link" onClick={() => setOpen(item.id)} aria-label={`Ver el detalle de la consulta del ${formatDate(item.created_at)}`}>
                        {formatDate(item.created_at)}
                      </button>
                    </td>
                    <td>{item.artifact ?? "-"}</td>
                    <td>{item.mode === "razonamiento" ? "razonamiento" : "literal"}</td>
                    <td className="mono">{item.model ?? "-"}</td>
                    <td className="num">{item.tokens === null ? "-" : formatTokens(item.tokens)}</td>
                    <td className="num">
                      {item.outcome.startsWith("rejected") ? "-" : formatUsd(item.cost_usd)}
                      {item.cost_estimated && <span title="Costo estimado con precios configurados"> *</span>}
                    </td>
                    <td className="num">{item.outcome.startsWith("rejected") ? "-" : formatLatency(item.latency_ms)}</td>
                    <td>
                      <span className={OUTCOME_LABEL[item.outcome].className} title={item.reject_reason ?? undefined}>
                        {OUTCOME_LABEL[item.outcome].text}
                      </span>
                      {item.reject_reason && item.outcome !== "error" && <span className="reason"> {item.reject_reason}</span>}
                    </td>
                    <td>{item.rating ? RATING_LABEL[item.rating] : <span className="muted">-</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="pager">
            <button className="btn btn-small" disabled={page <= 1} onClick={() => setPage(page - 1)}>
              Anterior
            </button>
            <span className="muted">
              Página {page} de {pages} · {data.total} {data.total === 1 ? "consulta" : "consultas"}
            </span>
            <button className="btn btn-small" disabled={page >= pages} onClick={() => setPage(page + 1)}>
              Siguiente
            </button>
          </div>
        </>
      )}
      {open && <Detail id={open} onClose={() => setOpen(null)} />}
    </section>
  );
}
