import { ActionIcon, Button, Group, Modal, Text } from "@mantine/core";
import { IconPlus, IconTrash } from "@tabler/icons-react";
import { useState } from "react";
import type { ConversationSummary } from "../api/types";

interface Props {
  conversations: ConversationSummary[];
  /** La conversación abierta, si hay una guardada. */
  activeId: string | null;
  loading?: boolean;
  /** Días que se guardan las conversaciones (feature 015); se omite si no se conoce. */
  retentionDays?: number;
  onOpen: (id: string) => void;
  onNew: () => void;
  /** Borrar una conversación o todas; sin ellos la lista no ofrece borrar. */
  onDelete?: (id: string) => void;
  onDeleteAll?: () => void;
}

/** "2026-11-04T16:20:00Z" como fecha corta; si no se entiende, vacío. */
export function shortDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("es", { day: "numeric", month: "short" }).format(date);
}

type Confirm = { kind: "one"; conversation: ConversationSummary } | { kind: "all" } | null;

/** Lista de conversaciones guardadas de la persona (feature 015): la más reciente primero, con "Nueva conversación" y,
 * con confirmación, borrar una o todas. */
export function ConversationList({
  conversations,
  activeId,
  loading = false,
  retentionDays,
  onOpen,
  onNew,
  onDelete,
  onDeleteAll,
}: Props) {
  const [confirm, setConfirm] = useState<Confirm>(null);

  return (
    <section className="conversation-list" aria-label="Conversaciones guardadas">
      <Group justify="space-between" align="center" gap="xs" wrap="wrap">
        <Text component="h2" className="sidebar-title">
          Conversaciones
        </Text>
        <Button variant="light" size="compact-sm" leftSection={<IconPlus size={14} />} onClick={onNew}>
          Nueva conversación
        </Button>
      </Group>
      {loading && (
        <Text c="dimmed" fz="sm">
          Cargando conversaciones...
        </Text>
      )}
      {!loading && conversations.length === 0 && (
        <Text c="dimmed" fz="sm">
          Todavía no tienes conversaciones guardadas.
        </Text>
      )}
      <ul>
        {conversations.map((conversation) => (
          <li key={conversation.id}>
            <button
              type="button"
              className={`conversation-item${conversation.id === activeId ? " active" : ""}`}
              aria-current={conversation.id === activeId ? "true" : undefined}
              onClick={() => onOpen(conversation.id)}
              title={conversation.title}
            >
              <span className="conversation-title">{conversation.title}</span>
              <span className="conversation-date">{shortDate(conversation.updated_at)}</span>
            </button>
            {onDelete && (
              <ActionIcon
                variant="subtle"
                size="sm"
                color="gray"
                aria-label={`Borrar conversación: ${conversation.title}`}
                onClick={() => setConfirm({ kind: "one", conversation })}
              >
                <IconTrash size={14} />
              </ActionIcon>
            )}
          </li>
        ))}
      </ul>
      {onDeleteAll && conversations.length > 0 && (
        <Button variant="subtle" size="compact-xs" onClick={() => setConfirm({ kind: "all" })}>
          Borrar todas
        </Button>
      )}
      {retentionDays !== undefined && retentionDays > 0 && (
        <Text c="dimmed" fz="xs">
          {`Tus conversaciones se guardan ${retentionDays} días sin actividad y puedes borrarlas cuando quieras.`}
        </Text>
      )}

      {confirm && (
        <Modal
          opened
          onClose={() => setConfirm(null)}
          centered
          title={confirm.kind === "all" ? "Borrar todas las conversaciones" : "Borrar la conversación"}
        >
          <Text>
            {confirm.kind === "all"
              ? "Se borrarán todas tus conversaciones guardadas. No se puede deshacer."
              : `Se borrará «${confirm.conversation.title}». No se puede deshacer.`}
          </Text>
          <Group justify="flex-end" mt="md">
            <Button variant="default" onClick={() => setConfirm(null)}>
              Cancelar
            </Button>
            <Button
              color="red"
              onClick={() => {
                if (confirm.kind === "all") onDeleteAll?.();
                else onDelete?.(confirm.conversation.id);
                setConfirm(null);
              }}
            >
              Borrar
            </Button>
          </Group>
        </Modal>
      )}
    </section>
  );
}
