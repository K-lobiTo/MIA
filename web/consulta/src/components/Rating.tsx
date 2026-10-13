import { Button, Group, Stack, Text, Textarea } from "@mantine/core";
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
    <Stack gap="xs" mt="xs">
      <Group gap="xs" align="center">
        <Text span c="dimmed" fz="sm">
          ¿Te sirvió esta respuesta?
        </Text>
        <Button
          type="button"
          size="compact-sm"
          variant={rating === "util" ? "filled" : "default"}
          aria-pressed={rating === "util"}
          disabled={feedback.isPending}
          onClick={() => submit("util")}
        >
          Útil
        </Button>
        <Button
          type="button"
          size="compact-sm"
          variant={rating === "no_util" ? "filled" : "default"}
          aria-pressed={rating === "no_util"}
          disabled={feedback.isPending}
          onClick={() => submit("no_util")}
        >
          No útil
        </Button>
        {failed && (
          <Text span role="alert" c="dimmed" fz="sm">
            No se pudo guardar tu calificación. Intenta de nuevo.
          </Text>
        )}
      </Group>
      {rating && (
        <Stack gap="xs" maw={420}>
          <Textarea
            aria-label="Comentario (opcional)"
            autosize
            minRows={2}
            maxLength={1000}
            placeholder="Comentario (opcional)"
            value={draft}
            onChange={(event) => setDraft(event.currentTarget.value)}
          />
          <Group>
            <Button
              type="button"
              size="compact-sm"
              variant="default"
              disabled={feedback.isPending || draft.trim() === (comment ?? "")}
              onClick={() => submit(rating, draft)}
            >
              Enviar comentario
            </Button>
          </Group>
        </Stack>
      )}
    </Stack>
  );
}
