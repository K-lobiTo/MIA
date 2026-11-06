import { ActionIcon, Button, Stack, Text, Title, Tooltip, Transition } from "@mantine/core";
import { IconArrowDown, IconArrowUp } from "@tabler/icons-react";
import { useCallback, useEffect, useRef, useState } from "react";
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
  /** Escribir un ejemplo en el campo de la pregunta (sin enviarlo); sin él los ejemplos son solo texto. */
  onExample?: (text: string) => void;
}

/** Margen en píxeles para considerar que la conversación ya está arriba o abajo del todo. */
const EDGE = 80;

export function Conversation({ exchanges, onRetry, literalAvailable, busy, mode, modeNames, onRate, onExample }: Props) {
  const endRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  // Si hay más conversación arriba o abajo de lo que se ve: muestran los botones de saltar al primer y al último mensaje.
  const [scrollable, setScrollable] = useState({ above: false, below: false });

  const measure = useCallback(() => {
    const list = listRef.current;
    if (!list) return;
    const above = list.scrollTop > EDGE;
    const below = list.scrollHeight - list.scrollTop - list.clientHeight > EDGE;
    setScrollable((previous) => (previous.above === above && previous.below === below ? previous : { above, below }));
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ block: "end" });
    measure();
  }, [exchanges, measure]);

  const scrollTo = (top: number) => listRef.current?.scrollTo?.({ top, behavior: "smooth" });

  return (
    <div className="messages-wrap">
      <div className="messages" ref={listRef} onScroll={measure}>
        {exchanges.length === 0 && (
          <Stack className="empty" gap="xs" align="center">
            <Title order={2} fz="1.3rem">
              Pregunta sobre los documentos de tu programa
            </Title>
            <Text c="dimmed">
              Elige los dominios y escribe tu pregunta{onExample ? ", o toca un ejemplo para escribirlo" : ". Por ejemplo"}:
            </Text>
            <Stack gap="xs" align="stretch" w="100%">
              {examplesFor(mode).map((example) =>
                onExample ? (
                  <Button
                    key={example}
                    variant="light"
                    size="sm"
                    h="auto"
                    py={8}
                    styles={{ label: { whiteSpace: "normal", textAlign: "left" } }}
                    onClick={() => onExample(example)}
                  >
                    {example}
                  </Button>
                ) : (
                  <Text key={example} c="dimmed" fz="sm">
                    {example}
                  </Text>
                ),
              )}
            </Stack>
          </Stack>
        )}
        {exchanges.map((exchange) => (
          <Exchange key={exchange.localId} exchange={exchange} onRetry={onRetry} literalAvailable={literalAvailable} busy={busy} modeNames={modeNames} onRate={onRate} />
        ))}
        <div ref={endRef} />
      </div>
      <Stack className="scroll-buttons" gap="xs" aria-label="Moverse por la conversación">
        <Transition mounted={scrollable.above} transition="fade" duration={150}>
          {(styles) => (
            <Tooltip label="Ir al primer mensaje" position="left" withArrow>
              <ActionIcon
                variant="default"
                radius="xl"
                size="lg"
                style={styles}
                aria-label="Ir al primer mensaje"
                onClick={() => scrollTo(0)}
              >
                <IconArrowUp size={18} />
              </ActionIcon>
            </Tooltip>
          )}
        </Transition>
        <Transition mounted={scrollable.below} transition="fade" duration={150}>
          {(styles) => (
            <Tooltip label="Ir al último mensaje" position="left" withArrow>
              <ActionIcon
                variant="default"
                radius="xl"
                size="lg"
                style={styles}
                aria-label="Ir al último mensaje"
                onClick={() => scrollTo(listRef.current?.scrollHeight ?? 0)}
              >
                <IconArrowDown size={18} />
              </ActionIcon>
            </Tooltip>
          )}
        </Transition>
      </Stack>
    </div>
  );
}
