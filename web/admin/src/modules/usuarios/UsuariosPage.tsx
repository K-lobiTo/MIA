import { Button, Group, Modal, Text } from "@mantine/core";
import { IconPlus } from "@tabler/icons-react";
import { useState } from "react";
import { useConsultaUsers, useResetConsultaPassword, useUpdateConsultaUser } from "../../api/consultaUsers";
import { useInventory } from "../../api/inventory";
import type { ConsultaUser } from "../../api/types";
import { useMe } from "../../auth/session";
import { Notice } from "../../components/Notice";
import { PasswordReveal } from "./PasswordReveal";
import { UserCard } from "./UserCard";
import { UserForm } from "./UserForm";
import { PRIVACY_TEXT } from "./usuariosUtils";
import "./usuarios.css";

type DialogState =
  | { kind: "new" }
  | { kind: "reset"; user: ConsultaUser }
  | { kind: "reveal"; username: string; password: string; reset: boolean };

/** Módulo "Usuarios de la Consulta": quienes inician sesión en la Consulta para guardar sus conversaciones. Cada cuenta de
 * administración gestiona los de su alcance (la API hace cumplir el permiso). La contraseña se muestra una sola vez. */
export function UsuariosPage() {
  const me = useMe();
  const users = useConsultaUsers();
  const inventory = useInventory();
  const update = useUpdateConsultaUser();
  const reset = useResetConsultaPassword();
  const [dialog, setDialog] = useState<DialogState | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const close = () => setDialog(null);

  async function toggleActive(user: ConsultaUser) {
    setActionError(null);
    try {
      await update.mutateAsync({ id: user.id, active: !user.active });
    } catch (caught) {
      setActionError(caught instanceof Error ? caught.message : "No se pudo cambiar el estado.");
    }
  }

  async function confirmReset(user: ConsultaUser) {
    setActionError(null);
    try {
      const result = await reset.mutateAsync({ id: user.id });
      setDialog({ kind: "reveal", username: user.username, password: result.password, reset: true });
    } catch (caught) {
      close();
      setActionError(caught instanceof Error ? caught.message : "No se pudo restablecer la contraseña.");
    }
  }

  return (
    <>
      <Group justify="space-between" align="center" gap="md">
        <h1>Usuarios de la Consulta</h1>
        <Button leftSection={<IconPlus size={16} />} onClick={() => setDialog({ kind: "new" })}>
          Registrar usuario
        </Button>
      </Group>
      <Text c="dimmed">
        Las personas con usuario inician sesión en la Consulta con su usuario y contraseña para volver a ver y retomar sus
        conversaciones. {PRIVACY_TEXT}
      </Text>
      {actionError && <Notice tone="danger">{actionError}</Notice>}
      {users.isPending && <Text c="dimmed">Cargando usuarios...</Text>}
      {users.isError && (
        <Notice tone="danger">
          No se pudieron cargar los usuarios: {users.error.message}{" "}
          <Button variant="default" size="compact-sm" onClick={() => users.refetch()}>
            Reintentar
          </Button>
        </Notice>
      )}
      {users.data && (
        <div className="user-list">
          {users.data.users.map((user) => (
            <UserCard
              key={user.id}
              user={user}
              busy={update.isPending || reset.isPending}
              onToggleActive={() => void toggleActive(user)}
              onResetPassword={() => setDialog({ kind: "reset", user })}
            />
          ))}
          {users.data.users.length === 0 && (
            <Text c="dimmed">Todavía no hay usuarios registrados. Registra el primero con "Registrar usuario".</Text>
          )}
        </div>
      )}

      {dialog?.kind === "new" && (
        <UserForm
          units={inventory.data?.units ?? []}
          isGlobal={Boolean(me?.is_global)}
          onClose={close}
          onCreated={(created) =>
            setDialog({ kind: "reveal", username: created.username, password: created.password, reset: false })
          }
        />
      )}
      {dialog?.kind === "reset" && (
        <Modal opened onClose={close} centered title={`Restablecer la contraseña de ${dialog.user.username}`}>
          <Text>
            La contraseña actual dejará de funcionar y se cerrarán todas sus sesiones abiertas. Se generará una nueva que
            verás una sola vez.
          </Text>
          <Group justify="flex-end" mt="md">
            <Button variant="default" onClick={close} disabled={reset.isPending}>
              Cancelar
            </Button>
            <Button onClick={() => void confirmReset(dialog.user)} loading={reset.isPending}>
              Restablecer
            </Button>
          </Group>
        </Modal>
      )}
      {dialog?.kind === "reveal" && (
        <PasswordReveal username={dialog.username} password={dialog.password} reset={dialog.reset} onClose={close} />
      )}
    </>
  );
}
