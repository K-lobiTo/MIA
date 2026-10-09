import { useEffect, useRef } from "react";
import type { ModeId, Rating } from "../api/types";
import { examplesFor } from "../state/examples";
import type { Exchange as ExchangeData } from "../state/conversation";
import { Exchange } from "./Exchange";

interface Props {
  exchanges: ExchangeData[];
  onRetry: (exchange: ExchangeData, mode?: "literal") => void;
  literalAvailable: boolean;
  busy: boolean;
  /** Modo con el que se preguntaría: los ejemplos de la conversación vacía son los de ese modo. */
  mode: ModeId;
  modeNames: Record<string, string>;
  onRate: (localId: string, rating: Rating, comment?: string) => void;
}

export function Conversation({ exchanges, onRetry, literalAvailable, busy, mode, modeNames, onRate }: Props) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ block: "end" });
  }, [exchanges]);

  return (
    <div className="messages">
      {exchanges.length === 0 && (
        <div className="empty">
          <h2>Pregunta sobre los documentos de tu unidad</h2>
          <p className="muted">Elige los dominios y escribe tu pregunta. Por ejemplo:</p>
          <ul>
            {examplesFor(mode).map((example) => (
              <li key={example}>{example}</li>
            ))}
          </ul>
        </div>
      )}
      {exchanges.map((exchange) => (
        <Exchange key={exchange.localId} exchange={exchange} onRetry={onRetry} literalAvailable={literalAvailable} busy={busy} modeNames={modeNames} onRate={onRate} />
      ))}
      <div ref={endRef} />
    </div>
  );
}
