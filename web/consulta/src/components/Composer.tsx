import { useRef, useState } from "react";

export const MAX_QUESTION_LENGTH = 2000;
const COUNTER_FROM = 1800;

interface Props {
  /** Cantidad de dominios seleccionados: sin ninguno no se puede preguntar. */
  selectedCount: number;
  /** Hay una consulta en curso: no se envía otra hasta que llegue la respuesta (FR-019). */
  busy: boolean;
  /** Motivo por el que el envío está bloqueado (tope alcanzado, modo no disponible), si lo hay. */
  blockedReason: string | null;
  /** Mensaje de la API para la última pregunta rechazada por su contenido; no borra lo escrito. */
  rejection: string | null;
  onSend: (question: string) => void;
}

export function Composer({ selectedCount, busy, blockedReason, rejection, onSend }: Props) {
  const [text, setText] = useState("");
  const areaRef = useRef<HTMLTextAreaElement>(null);

  const hint = blockedReason ?? (selectedCount === 0 ? "Elige al menos un dominio." : null);
  const canSend = !busy && !hint && text.trim().length > 0;

  const send = () => {
    if (!canSend) return;
    onSend(text.trim());
    setText("");
    if (areaRef.current) areaRef.current.style.height = "";
  };

  return (
    <form
      className="composer"
      onSubmit={(event) => {
        event.preventDefault();
        send();
      }}
    >
      {rejection && (
        <p className="notice notice-danger" role="alert">
          {rejection}
        </p>
      )}
      <div className="composer-row">
        <label className="sr-only" htmlFor="question">
          Tu pregunta
        </label>
        <textarea
          id="question"
          ref={areaRef}
          rows={1}
          maxLength={MAX_QUESTION_LENGTH}
          value={text}
          placeholder={hint ? "" : "Escribe tu pregunta..."}
          onChange={(event) => {
            setText(event.target.value);
            event.target.style.height = "";
            event.target.style.height = `${Math.min(event.target.scrollHeight, 160)}px`;
          }}
          onKeyDown={(event) => {
            // Enter envía; Mayúsculas+Enter agrega una línea.
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              send();
            }
          }}
        />
        <button type="submit" className="btn btn-primary" disabled={!canSend}>
          Preguntar
        </button>
      </div>
      <div className="composer-hint">
        <span role={hint ? "status" : undefined}>{hint ?? ""}</span>
        {text.length >= COUNTER_FROM && (
          <span>
            {text.length} / {MAX_QUESTION_LENGTH}
          </span>
        )}
      </div>
    </form>
  );
}
