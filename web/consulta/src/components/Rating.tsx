import { useState } from "react";
import { useFeedback } from "../api/consulta";
import type { Rating as RatingValue } from "../api/types";

interface Props {
  queryId: string;
  rating: RatingValue | undefined;
  comment: string | undefined;
  /** Se llama cuando la API ya guardó la calificación (y el comentario, si lo hay). */
  onRate: (rating: RatingValue, comment?: string) => void;
}

/** Calificación de una respuesta: útil o no útil, con comentario opcional (CON-8). Una nueva reemplaza a la anterior. */
export function Rating({ queryId, rating, comment, onRate }: Props) {
  const feedback = useFeedback();
  const [draft, setDraft] = useState(comment ?? "");
  const [failed, setFailed] = useState(false);

  const submit = (value: RatingValue, text?: string) => {
    setFailed(false);
    feedback.mutate(
      { queryId, rating: value, comment: text },
      { onSuccess: () => onRate(value, text?.trim() || undefined), onError: () => setFailed(true) },
    );
  };

  return (
    <div className="rating">
      <span className="muted">¿Te sirvió esta respuesta?</span>
      <button
        type="button"
        className="btn btn-small"
        aria-pressed={rating === "util"}
        disabled={feedback.isPending}
        onClick={() => submit("util")}
      >
        Útil
      </button>
      <button
        type="button"
        className="btn btn-small"
        aria-pressed={rating === "no_util"}
        disabled={feedback.isPending}
        onClick={() => submit("no_util")}
      >
        No útil
      </button>
      {failed && (
        <span role="alert" className="muted">
          No se pudo guardar tu calificación. Intenta de nuevo.
        </span>
      )}
      {rating && (
        <div className="rating-comment">
          <label className="sr-only" htmlFor={`comment-${queryId}`}>
            Comentario (opcional)
          </label>
          <textarea
            id={`comment-${queryId}`}
            rows={2}
            maxLength={1000}
            placeholder="Comentario (opcional)"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
          />
          <button
            type="button"
            className="btn btn-small"
            disabled={feedback.isPending || draft.trim() === (comment ?? "")}
            onClick={() => submit(rating, draft)}
          >
            Enviar comentario
          </button>
        </div>
      )}
    </div>
  );
}
