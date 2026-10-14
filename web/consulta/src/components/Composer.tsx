import { Button, Textarea } from "@mantine/core";
import { useEffect, useState } from "react";
import type { ModeId } from "../api/types";
import type { Availability } from "../state/modes";
import { ModePicker } from "./ModePicker";
import { Notice } from "./Notice";

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
  /** Pregunta que la API rechazó por su contenido: vuelve al campo para no perder lo escrito. */
  restore: { text: string; n: number } | null;
  /** Modos disponibles y el elegido: el selector va a la izquierda del campo. Nulo mientras no hay configuración. */
  availability: Availability | null;
  onModeChange: (mode: ModeId) => void;
  onSend: (question: string) => void;
}

export function Composer({ selectedCount, busy, blockedReason, rejection, restore, availability, onModeChange, onSend }: Props) {
  const [text, setText] = useState("");

  // `n` cambia en cada rechazo, así que dos rechazos seguidos de la misma pregunta también la restauran.
  useEffect(() => {
    if (restore) setText(restore.text);
  }, [restore]);

  const hint = blockedReason ?? (selectedCount === 0 ? "Elige al menos un dominio." : null);
  const canSend = !busy && !hint && text.trim().length > 0;

  const send = () => {
    if (!canSend) return;
    onSend(text.trim());
    setText("");
  };

  return (
    <form
      className="composer"
      onSubmit={(event) => {
        event.preventDefault();
        send();
      }}
    >
      {availability?.changed && availability.effective && (
        <Notice tone="warn">
          El modo que usabas ya no está disponible. Ahora se usa «{availability.modes.find((m) => m.id === availability.effective)?.name}».
        </Notice>
      )}
      {rejection && <Notice tone="danger">{rejection}</Notice>}
      <div className="composer-row">
        {availability && <ModePicker availability={availability} onChange={onModeChange} />}
        <Textarea
          id="question"
          aria-label="Tu pregunta"
          autosize
          minRows={1}
          maxRows={6}
          maxLength={MAX_QUESTION_LENGTH}
          value={text}
          placeholder={hint ? "" : "Escribe tu pregunta..."}
          onChange={(event) => setText(event.currentTarget.value)}
          onKeyDown={(event) => {
            // Enter envía; Mayúsculas+Enter agrega una línea.
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              send();
            }
          }}
        />
        <Button type="submit" size="md" disabled={!canSend}>
          Preguntar
        </Button>
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
