import { useEffect, useRef } from "react";
import type { Rating } from "../api/types";
import type { Exchange as ExchangeData } from "../state/conversation";
import { Exchange } from "./Exchange";

interface Props {
  exchanges: ExchangeData[];
  onRetry: (exchange: ExchangeData, mode?: "literal") => void;
  literalAvailable: boolean;
  modeNames: Record<string, string>;
  onRate: (localId: string, rating: Rating, comment?: string) => void;
}

export function Conversation({ exchanges, onRetry, literalAvailable, modeNames, onRate }: Props) {
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
            <li>¿Qué se acordó sobre las becas en las últimas actas?</li>
            <li>¿Qué requisitos de graduación tiene el plan de estudios?</li>
          </ul>
        </div>
      )}
      {exchanges.map((exchange) => (
        <Exchange key={exchange.localId} exchange={exchange} onRetry={onRetry} literalAvailable={literalAvailable} modeNames={modeNames} onRate={onRate} />
      ))}
      <div ref={endRef} />
    </div>
  );
}
