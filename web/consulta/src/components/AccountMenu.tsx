import { Button, Menu, Modal, PasswordInput, Stack } from "@mantine/core";
import { IconUser } from "@tabler/icons-react";
import { useState } from "react";
import { ApiError } from "../api/client";
import { useChangePassword, useLogout } from "../api/auth";
import { authErrorMessage, lockMessage } from "../state/chat";
import { Notice } from "./Notice";

interface Props {
  username: string;
  /** Después de cerrar sesión (limpia la conversación en pantalla). */
  onLoggedOut: () => void;
}

/** Nombre de la persona con la sesión abierta, con "Cambiar contraseña" y "Cerrar sesión". */
export function AccountMenu({ username, onLoggedOut }: Props) {
  const logout = useLogout();
  const [changing, setChanging] = useState(false);

  async function close() {
    try {
      await logout.mutateAsync();
    } catch {
      // El servidor no respondió: la sesión local ya se olvidó.
    }
    onLoggedOut();
  }

  return (
    <>
      <Menu position="bottom-end" withinPortal>
        <Menu.Target>
          <Button variant="default" size="compact-sm" leftSection={<IconUser size={14} />} aria-label="Cuenta">
            {username}
          </Button>
        </Menu.Target>
        <Menu.Dropdown>
          <Menu.Item onClick={() => setChanging(true)}>Cambiar contraseña</Menu.Item>
          <Menu.Item onClick={() => void close()}>Cerrar sesión</Menu.Item>
        </Menu.Dropdown>
      </Menu>
      {changing && <ChangePasswordDialog onClose={() => setChanging(false)} />}
    </>
  );
}

function ChangePasswordDialog({ onClose }: { onClose: () => void }) {
  const change = useChangePassword();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await change.mutateAsync({ current_password: current, new_password: next });
      setDone(true);
    } catch (caught) {
      if (caught instanceof ApiError) {
        setError(
          caught.code === "too_many_attempts"
            ? lockMessage(caught.retryAfter)
            : (authErrorMessage(caught.code) ?? caught.message),
        );
      } else {
        setError("No se pudo cambiar la contraseña.");
      }
    }
  }

  return (
    <Modal opened onClose={onClose} centered title="Cambiar contraseña">
      {done ? (
        <Stack>
          <Notice tone="ok">Contraseña cambiada. Tus otras sesiones se cerraron.</Notice>
          <Button onClick={onClose}>Cerrar</Button>
        </Stack>
      ) : (
        <form onSubmit={submit}>
          <Stack>
            <PasswordInput label="Contraseña actual" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.currentTarget.value)} />
            <PasswordInput
              label="Contraseña nueva"
              description="Al menos 10 caracteres."
              autoComplete="new-password"
              value={next}
              onChange={(e) => setNext(e.currentTarget.value)}
            />
            {error && <Notice tone="danger">{error}</Notice>}
            <Button type="submit" loading={change.isPending} disabled={!current || next.length < 10}>
              Cambiar contraseña
            </Button>
          </Stack>
        </form>
      )}
    </Modal>
  );
}
