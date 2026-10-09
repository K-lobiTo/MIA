import type { Rating as RatingValue } from "../api/types";
import { Answer } from "../format/Answer";
import { Rating } from "./Rating";
import { describeError } from "../state/errors";
import { uniqueDocuments } from "../state/sources";
import { formatLatency, type Exchange as ExchangeData } from "../state/conversation";

interface Props {
  exchange: ExchangeData;
  /** Vuelve a enviar la misma pregunta como un intercambio nuevo. */
  onRetry: (exchange: ExchangeData, mode?: "literal") => void;
  /** El modo literal está disponible: solo entonces se ofrece reintentar en literal. */
  literalAvailable: boolean;
  /** Hay una consulta en curso: no se puede reintentar otra en paralelo (FR-019). */
  busy: boolean;
  /** Nombre visible de cada modo, para el pie de la respuesta. */
  modeNames: Record<string, string>;
  onRate: (localId: string, rating: RatingValue, comment?: string) => void;
}

export function Exchange({ exchange, onRetry, literalAvailable, busy, modeNames, onRate }: Props) {
  const { question, status, response, error } = exchange;

  return (
    <>
      <div className="message user">
        <p>{question}</p>
      </div>

      {status === "pending" && (
        <div className="message" aria-live="polite">
          <p className="typing">
            Buscando en {exchange.domainIds.length} {exchange.domainIds.length === 1 ? "dominio" : "dominios"}...
          </p>
          {exchange.mode === "razonamiento" && (
            <p className="muted">El modo con razonamiento puede tardar más de un minuto.</p>
          )}
        </div>
      )}

      {status === "failed" && error && <Failure exchange={exchange} onRetry={onRetry} literalAvailable={literalAvailable} busy={busy} />}

      {(status === "answered" || status === "no_info") && response && (
        <div className={`message${status === "no_info" ? " info" : ""}`}>
          <Answer text={response.answer} />
          {status === "answered" && response.sources.length > 0 && <Sources exchange={exchange} />}
          <p className="footnote">
            {modeNames[response.mode] ?? response.mode} · {formatLatency(response.latency_ms)}
          </p>
          <Rating
            queryId={response.id}
            rating={exchange.rating}
            comment={exchange.ratingComment}
            onRate={(rating, comment) => onRate(exchange.localId, rating, comment)}
          />
        </div>
      )}
    </>
  );
}

function Sources({ exchange }: { exchange: ExchangeData }) {
  const sources = exchange.response?.sources ?? [];
  const documents = uniqueDocuments(sources);
  return (
    <div className="sources">
      <div className="sources-title">Fuentes</div>
      <ul>
        {documents.map((doc) => (
          <li key={`${doc.domain}/${doc.document}`}>
            {doc.document} <span className="muted">({doc.domain})</span>
          </li>
        ))}
      </ul>
      <details>
        <summary>Ver fragmentos ({sources.length})</summary>
        {sources.map((source, index) => (
          <div className="excerpt" key={index}>
            <div className="excerpt-title">
              [{index + 1}] {source.document}
            </div>
            <p>{source.excerpt.replace(/\s+/g, " ").trim()}</p>
          </div>
        ))}
      </details>
    </div>
  );
}

function Failure({ exchange, onRetry, literalAvailable, busy }: Pick<Props, "exchange" | "onRetry" | "literalAvailable" | "busy">) {
  const view = describeError(exchange.error!, exchange.mode, literalAvailable);
  return (
    <div className="message error" role="alert">
      <p>{view.message}</p>
      {(view.canRetry || view.offerLiteral) && (
        <div className="message-actions">
          {view.canRetry && (
            <button type="button" className="btn btn-small" disabled={busy} onClick={() => onRetry(exchange)}>
              Reintentar
            </button>
          )}
          {view.offerLiteral && (
            <button type="button" className="btn btn-small" disabled={busy} onClick={() => onRetry(exchange, "literal")}>
              Reintentar en modo literal
            </button>
          )}
        </div>
      )}
    </div>
  );
}
