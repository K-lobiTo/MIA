import { AppShell, Button, Divider, Paper, ScrollArea, Text } from "@mantine/core";
import { IconLogin } from "@tabler/icons-react";
import type { ConversationSummary, Domain } from "../api/types";
import { ColorSchemeToggle } from "./ColorSchemeToggle";
import { ConversationList } from "./ConversationList";
import { DomainPicker } from "./DomainPicker";
import { Notice } from "./Notice";

/** Lo que necesita la lista de conversaciones guardadas (feature 015); nulo si la persona no tiene sesión o el servidor no guarda. */
export interface SidebarHistory {
  conversations: ConversationSummary[];
  activeId: string | null;
  loading: boolean;
  retentionDays?: number;
  onOpen: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  onDeleteAll: () => void;
}

interface Props {
  domains: Domain[];
  selected: string[];
  onSelect: (ids: string[]) => void;
  history: SidebarHistory | null;
  /** Con sesión pero el servidor no guarda conversaciones (retención en 0). */
  savingOff?: boolean;
  /** Sin sesión y con el guardado activo: abre el inicio de sesión. Se omite si no hay nada que ofrecer. */
  onLogin?: () => void;
}

/** Menú lateral de la Consulta, sobre el `AppShell.Navbar` de Mantine: las conversaciones guardadas arriba (ocupan el espacio
 * sobrante y se desplazan solas) y, separados por una línea, los dominios a consultar en una tarjeta fija abajo. Sin sesión,
 * en lugar de la lista hay una invitación a iniciar sesión. */
export function Sidebar({ domains, selected, onSelect, history, savingOff = false, onLogin }: Props) {
  const invite = history === null && !savingOff && onLogin !== undefined;
  const hasTop = history !== null || savingOff || invite;

  return (
    <AppShell.Navbar p="md" aria-label="Conversaciones y dominios">
      {/* En pantallas angostas el interruptor de apariencia no cabe en el encabezado y va aquí. */}
      <AppShell.Section hiddenFrom="sm" mb="md">
        <ColorSchemeToggle />
      </AppShell.Section>

      {hasTop && (
        <AppShell.Section grow component={ScrollArea} type="auto" offsetScrollbars scrollbarSize={6}>
          {history && (
            <ConversationList
              conversations={history.conversations}
              activeId={history.activeId}
              loading={history.loading}
              retentionDays={history.retentionDays}
              onOpen={history.onOpen}
              onNew={history.onNew}
              onDelete={history.onDelete}
              onDeleteAll={history.onDeleteAll}
            />
          )}
          {savingOff && (
            <Notice tone="info">El guardado de conversaciones está desactivado: lo que preguntes no se guarda.</Notice>
          )}
          {invite && (
            <Paper withBorder radius="md" p="md" className="sidebar-invite">
              <Text fw={700}>Guarda tus conversaciones</Text>
              <Text c="dimmed" fz="sm">
                Con un usuario puedes volver a ver y retomar lo que preguntaste, desde cualquier dispositivo.
              </Text>
              <Button variant="light" size="compact-sm" leftSection={<IconLogin size={14} />} onClick={onLogin}>
                Iniciar sesión
              </Button>
            </Paper>
          )}
        </AppShell.Section>
      )}

      {hasTop && <Divider my="md" />}

      <AppShell.Section>
        <Paper withBorder radius="md" p="sm" className="sidebar-domains">
          <DomainPicker domains={domains} selected={selected} onChange={onSelect} />
        </Paper>
      </AppShell.Section>
    </AppShell.Navbar>
  );
}
