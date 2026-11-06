import {
  Accordion,
  ActionIcon,
  Anchor,
  Avatar,
  Button,
  CopyButton,
  Divider,
  Group,
  List,
  Loader,
  Paper,
  Stack,
  Text,
  Tooltip,
} from "@mantine/core";
import { IconCheck, IconCopy, IconUser } from "@tabler/icons-react";
import { useState, type ReactNode } from "react";
import type { Rating as RatingValue } from "../api/types";
import { Answer } from "../format/Answer";
import { Rating } from "./Rating";
import { describeError } from "../state/errors";
import { previewExcerpt, uniqueDocuments } from "../state/sources";
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

/** Una burbuja con su avatar: la de MIA a la izquierda (con el ícono del sitio) y la de la persona a la derecha. Las
 * nuevas entran con una animación suave (`animate`); las de una conversación guardada aparecen sin ella. */
function Row({ user = false, animate, children }: { user?: boolean; animate: boolean; children: ReactNode }) {
  return (
    <Group wrap="nowrap" align="flex-start" gap="xs" className={`message-row${user ? " user" : ""}${animate ? " enter" : ""}`}>
      {user ? (
        <Avatar radius="xl" size="sm" color="vanilla" aria-hidden>
          <IconUser size={14} />
        </Avatar>
      ) : (
        <Avatar src="/favicon.svg" alt="MIA" radius="xl" size="sm" />
      )}
      {children}
    </Group>
  );
}

export function Exchange({ exchange, onRetry, literalAvailable, busy, modeNames, onRate }: Props) {
  const { question, status, response, error } = exchange;
  const animate = !exchange.stored;

  return (
    <>
      <Row user animate={animate}>
        <Paper shadow="sm" className="message user">
          <Text>{question}</Text>
        </Paper>
      </Row>

      {status === "pending" && (
        <Row animate={animate}>
          <Paper shadow="sm" className="message" aria-live="polite">
            <Group gap="xs">
              <Loader type="dots" size="sm" />
              <Text c="dimmed" fs="italic">
                Buscando en {exchange.domainIds.length} {exchange.domainIds.length === 1 ? "dominio" : "dominios"}...
              </Text>
            </Group>
            {exchange.mode === "razonamiento" && (
              <Text c="dimmed" fz="sm" mt={4}>
                El modo con razonamiento puede tardar más de un minuto.
              </Text>
            )}
          </Paper>
        </Row>
      )}

      {status === "failed" && error && (
        <Row animate={animate}>
          <Failure exchange={exchange} onRetry={onRetry} literalAvailable={literalAvailable} busy={busy} />
        </Row>
      )}

      {(status === "answered" || status === "no_info") && response && (
        <Row animate={animate}>
          <Paper shadow="sm" className={`message${status === "no_info" ? " info" : ""}`}>
            <Answer text={response.answer} />
            {status === "answered" && response.sources.length > 0 && <Sources exchange={exchange} />}
            <Group justify="space-between" align="center" mt="sm" gap="xs" wrap="nowrap">
              <Text fz="xs" c="dimmed">
                {modeNames[response.mode] ?? response.mode}
                {!exchange.stored && <> · {formatLatency(response.latency_ms)}</>}
              </Text>
              <CopyButton value={response.answer} timeout={2000}>
                {({ copied, copy }) => (
                  <Tooltip label={copied ? "Copiado" : "Copiar respuesta"} withArrow>
                    <ActionIcon
                      variant="subtle"
                      size="sm"
                      color={copied ? "teal" : undefined}
                      onClick={copy}
                      aria-label="Copiar respuesta"
                    >
                      {copied ? <IconCheck size={16} /> : <IconCopy size={16} />}
                    </ActionIcon>
                  </Tooltip>
                )}
              </CopyButton>
            </Group>
            {exchange.notSaved && (
              <Text fz="xs" c="dimmed" mt={4} role="status">
                Esta respuesta no se pudo guardar en tu historial.
              </Text>
            )}
            {!exchange.stored && (
              <Rating
                queryId={response.id}
                rating={exchange.rating}
                comment={exchange.ratingComment}
                onRate={(rating, comment) => onRate(exchange.localId, rating, comment)}
              />
            )}
          </Paper>
        </Row>
      )}
    </>
  );
}

function Sources({ exchange }: { exchange: ExchangeData }) {
  const sources = exchange.response?.sources ?? [];
  const documents = uniqueDocuments(sources);
  return (
    <>
      <Divider my="sm" />
      <Text fw={700} fz="sm" mb={4}>
        Fuentes
      </Text>
      <List size="sm" spacing={2}>
        {documents.map((doc) => (
          <List.Item key={`${doc.domain}/${doc.document}`}>
            {doc.document}{" "}
            <Text span c="dimmed" inherit>
              ({doc.domain})
            </Text>
          </List.Item>
        ))}
      </List>
      {/* Las conversaciones guardadas conservan el documento de cada fuente, no su fragmento. */}
      {sources.some((source) => source.excerpt) && (
        <Accordion variant="default" chevronPosition="left" mt="xs">
          <Accordion.Item value="fragmentos">
            <Accordion.Control>
              <Text fz="sm">Ver fragmentos ({sources.length})</Text>
            </Accordion.Control>
            <Accordion.Panel>
              <Stack gap="xs">
                {sources.map((source, index) => (
                  <Excerpt key={index} index={index + 1} document={source.document} text={source.excerpt} />
                ))}
              </Stack>
            </Accordion.Panel>
          </Accordion.Item>
        </Accordion>
      )}
    </>
  );
}

function Failure({ exchange, onRetry, literalAvailable, busy }: Pick<Props, "exchange" | "onRetry" | "literalAvailable" | "busy">) {
  const view = describeError(exchange.error!, exchange.mode, literalAvailable);
  return (
    <Paper shadow="sm" className="message error" role="alert">
      <Text>{view.message}</Text>
      {(view.canRetry || view.offerLiteral) && (
        <Group gap="xs" mt="sm">
          {view.canRetry && (
            <Button type="button" variant="default" size="compact-sm" disabled={busy} onClick={() => onRetry(exchange)}>
              Reintentar
            </Button>
          )}
          {view.offerLiteral && (
            <Button type="button" variant="default" size="compact-sm" disabled={busy} onClick={() => onRetry(exchange, "literal")}>
              Reintentar en modo literal
            </Button>
          )}
        </Group>
      )}
    </Paper>
  );
}

/** Un fragmento citado: solo el comienzo, con "Ver más" para leerlo completo (suelen ser muy largos). */
function Excerpt({ index, document, text }: { index: number; document: string; text: string }) {
  const [open, setOpen] = useState(false);
  const preview = previewExcerpt(text);
  return (
    <Paper className="excerpt" p="xs" radius="sm">
      <Text fw={600} fz="sm">
        [{index}] {document}
      </Text>
      <Text fz="sm">{open || !preview.truncated ? text.replace(/\s+/g, " ").trim() : preview.text}</Text>
      {preview.truncated && (
        <Anchor component="button" type="button" fz="sm" fw={600} aria-expanded={open} onClick={() => setOpen((value) => !value)}>
          {open ? "Ver menos" : "Ver más"}
        </Anchor>
      )}
    </Paper>
  );
}
