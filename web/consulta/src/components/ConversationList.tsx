import { ActionIcon, Button, Group, Menu, Modal, NavLink, Stack, Text, TextInput } from "@mantine/core";
import { IconDots, IconMessages, IconPencil, IconPlus, IconTrash } from "@tabler/icons-react";
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
  /** Borrar una conversación o todas, y cambiar el título de una; sin ellos la lista no lo ofrece. */
  onDelete?: (id: string) => void;
  onDeleteAll?: () => void;
  onRename?: (id: string, title: string) => void;
}

/** "2026-11-04T16:20:00Z" como fecha corta; si no se entiende, vacío. */
export function shortDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("es", { day: "numeric", month: "short" }).format(date);
}

type Dialog =
  | { kind: "delete"; conversation: ConversationSummary }
  | { kind: "rename"; conversation: ConversationSummary }
  | { kind: "all" }
  | null;

/** Lista de conversaciones guardadas de la persona (feature 015): la más reciente primero, con "Nueva conversación" y,
 * en el menú de cada una, renombrar y (con confirmación) borrar; además borrar todas. */
export function ConversationList({
  conversations,
  activeId,
  loading = false,
  retentionDays,
  onOpen,
  onNew,
  onDelete,
  onDeleteAll,
  onRename,
}: Props) {
  const [dialog, setDialog] = useState<Dialog>(null);
  const [draft, setDraft] = useState("");
  const hasMenu = Boolean(onDelete || onRename);

  const close = () => setDialog(null);

  return (
    <section className="conversation-list" aria-label="Conversaciones guardadas">
      <Group justify="space-between" align="center" gap="xs" wrap="wrap">
        <Text component="h2" className="sidebar-title">
          <IconMessages size={14} stroke={2} aria-hidden />
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
      <Stack component="ul" gap={2} p={0} m={0} style={{ listStyle: "none" }}>
        {conversations.map((conversation) => {
          const active = conversation.id === activeId;
          return (
            <Group key={conversation.id} component="li" gap={2} wrap="nowrap">
              <NavLink
                label={conversation.title}
                description={shortDate(conversation.updated_at)}
                active={active}
                aria-current={active ? "true" : undefined}
                title={conversation.title}
                onClick={() => onOpen(conversation.id)}
                style={{ flex: 1, minWidth: 0, borderRadius: "var(--mantine-radius-sm)" }}
                styles={{ body: { minWidth: 0 }, label: { overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" } }}
              />
              {hasMenu && (
                <Menu position="bottom-end" withinPortal shadow="md">
                  <Menu.Target>
                    <ActionIcon variant="subtle" size="sm" aria-label={`Opciones de la conversación: ${conversation.title}`}>
                      <IconDots size={16} />
                    </ActionIcon>
                  </Menu.Target>
                  <Menu.Dropdown>
                    {onRename && (
                      <Menu.Item
                        leftSection={<IconPencil size={14} />}
                        onClick={() => {
                          setDraft(conversation.title);
                          setDialog({ kind: "rename", conversation });
                        }}
                      >
                        Renombrar
                      </Menu.Item>
                    )}
                    {onDelete && (
                      <Menu.Item
                        color="red"
                        leftSection={<IconTrash size={14} />}
                        onClick={() => setDialog({ kind: "delete", conversation })}
                      >
                        Borrar
                      </Menu.Item>
                    )}
                  </Menu.Dropdown>
                </Menu>
              )}
            </Group>
          );
        })}
      </Stack>
      {onDeleteAll && conversations.length > 0 && (
        <Button variant="subtle" size="compact-xs" onClick={() => setDialog({ kind: "all" })}>
          Borrar todas
        </Button>
      )}
      {retentionDays !== undefined && retentionDays > 0 && (
        <Text c="dimmed" fz="xs">
          {`Tus conversaciones se guardan ${retentionDays} días sin actividad y puedes borrarlas cuando quieras.`}
        </Text>
      )}

      {dialog && dialog.kind !== "rename" && (
        <Modal
          opened
          onClose={close}
          centered
          title={dialog.kind === "all" ? "Borrar todas las conversaciones" : "Borrar la conversación"}
        >
          <Text>
            {dialog.kind === "all"
              ? "Se borrarán todas tus conversaciones guardadas. No se puede deshacer."
              : `Se borrará «${dialog.conversation.title}». No se puede deshacer.`}
          </Text>
          <Group justify="flex-end" mt="md">
            <Button variant="default" onClick={close}>
              Cancelar
            </Button>
            <Button
              color="red"
              onClick={() => {
                if (dialog.kind === "all") onDeleteAll?.();
                else onDelete?.(dialog.conversation.id);
                close();
              }}
            >
              Borrar
            </Button>
          </Group>
        </Modal>
      )}

      {dialog && dialog.kind === "rename" && (
        <Modal opened onClose={close} centered title="Renombrar la conversación">
          <form
            onSubmit={(event) => {
              event.preventDefault();
              const title = draft.trim();
              if (title) onRename?.(dialog.conversation.id, title);
              close();
            }}
          >
            <TextInput
              label="Título"
              value={draft}
              maxLength={80}
              data-autofocus
              onChange={(event) => setDraft(event.currentTarget.value)}
            />
            <Group justify="flex-end" mt="md">
              <Button variant="default" onClick={close}>
                Cancelar
              </Button>
              <Button type="submit" disabled={!draft.trim()}>
                Guardar
              </Button>
            </Group>
          </form>
        </Modal>
      )}
    </section>
  );
}
