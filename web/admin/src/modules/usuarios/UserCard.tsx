import { Button, Group, Paper, Text } from "@mantine/core";
import type { ConsultaUser } from "../../api/types";
import { StatusBadge } from "../../components/StatusBadge";
import { describeConversations, describeUserStatus, formatDateTime } from "./usuariosUtils";

interface Props {
  user: ConsultaUser;
  busy: boolean;
  onToggleActive: () => void;
  onResetPassword: () => void;
}

export function UserCard({ user, busy, onToggleActive, onResetPassword }: Props) {
  const status = describeUserStatus(user);
  return (
    <Paper component="article" withBorder p="md" radius="md" className="user-card" aria-label={user.username}>
      <Group gap="sm" wrap="wrap">
        <span className="user-name">{user.username}</span>
        <StatusBadge tone={status.tone}>{status.text}</StatusBadge>
      </Group>
      <dl className="user-meta">
        <dt>Programa</dt>
        <dd>
          {user.unit ? (
            user.unit.name
          ) : (
            <Text span c="dimmed">
              Ninguno (global)
            </Text>
          )}
        </dd>
        <dt>Último acceso</dt>
        <dd>{formatDateTime(user.last_login_at)}</dd>
        <dt>Conversaciones</dt>
        <dd>
          {describeConversations(user.conversation_count)}
          {user.last_activity_at && <> (última actividad: {formatDateTime(user.last_activity_at)})</>}
        </dd>
      </dl>
      <Group gap="xs" mt={4}>
        <Button variant="default" size="compact-sm" onClick={onToggleActive} disabled={busy}>
          {user.active ? "Desactivar" : "Reactivar"}
        </Button>
        <Button variant="default" size="compact-sm" onClick={onResetPassword} disabled={busy}>
          Restablecer contraseña
        </Button>
      </Group>
    </Paper>
  );
}
