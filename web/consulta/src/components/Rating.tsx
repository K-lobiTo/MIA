import { Button, Group, Stack, Text, Textarea, Transition } from "@mantine/core";
import { IconCheck } from "@tabler/icons-react";
import { useEffect, useRef, useState } from "react";
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
  // Aviso breve de que el comentario llegó a la API; se oculta solo.
  const [sentMessage, setSentMessage] = useState<string | null>(null);
  const [showSent, setShowSent] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
  useEffect(() => () => clearTimeout(timer.current), []);

  const confirmSent = (text: string) => {
    clearTimeout(timer.current);
    setSentMessage(text.trim() ? "Comentario enviado" : "Comentario eliminado");
    setShowSent(true);
    timer.current = setTimeout(() => setShowSent(false), 3000);
  };

  const submit = (value: RatingValue, text?: string) => {
    setFailed(false);
    setShowSent(false);
    feedback.mutate(
      { queryId, rating: value, comment: text },
      {
        onSuccess: () => {
          onRate(value, text?.trim() || undefined);
          if (text !== undefined) confirmSent(text);
        },
        onError: () => setFailed(true),
      },
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
              loading={feedback.isPending}
              disabled={feedback.isPending || draft.trim() === (comment ?? "")}
              onClick={() => submit(rating, draft)}
            >
              Enviar comentario
            </Button>
            {/* Región en vivo siempre presente para que los lectores de pantalla anuncien el mensaje. */}
            <div role="status" aria-live="polite">
              <Transition mounted={showSent} transition="fade-right" duration={250} timingFunction="ease">
                {(styles) => (
                  <Group gap={6} wrap="nowrap" style={styles}>
                    <IconCheck size={16} stroke={2.5} color="var(--mantine-primary-color-filled)" aria-hidden />
                    <Text span fz="sm" fw={600}>
                      {sentMessage}
                    </Text>
                  </Group>
                )}
              </Transition>
            </div>
          </Group>
        </Stack>
      )}
    </Stack>
  );
}
