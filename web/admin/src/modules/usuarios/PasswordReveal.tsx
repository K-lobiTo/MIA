import { Button, Group, Modal } from "@mantine/core";
import { useState } from "react";
import { Notice } from "../../components/Notice";
import { ONE_TIME_PASSWORD_TEXT } from "./usuariosUtils";

interface Props {
  username: string;
  password: string;
  // Restablecida: la anterior ya dejó de funcionar.
  reset?: boolean;
  onClose: () => void;
}

/** Muestra la contraseña completa una sola vez: después de cerrar este diálogo no se puede volver a ver. */
export function PasswordReveal({ username, password, reset, onClose }: Props) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(password);
      setCopied(true);
    } catch {
      // Sin permiso para el portapapeles: la contraseña está seleccionable en el cuadro de arriba.
      setCopied(false);
    }
  }

  return (
    // Solo se cierra con "Ya la entregué": un clic o Escape por accidente perdería la única vista de la contraseña.
    <Modal
      opened
      onClose={onClose}
      size="lg"
      centered
      withCloseButton={false}
      closeOnClickOutside={false}
      closeOnEscape={false}
      title={`${reset ? "Contraseña restablecida" : "Usuario registrado"}: ${username}`}
    >
      <Notice tone="warn">
        <strong>{ONE_TIME_PASSWORD_TEXT}</strong>
        {reset && " La anterior ya dejó de funcionar y se cerraron sus sesiones."}
      </Notice>
      <div className="key-box" data-testid="contrasena-completa">
        {password}
      </div>
      <Group justify="space-between" mt="md">
        <Button variant="default" onClick={copy}>
          {copied ? "Copiada" : "Copiar contraseña"}
        </Button>
        <Button onClick={onClose}>Ya la entregué</Button>
      </Group>
    </Modal>
  );
}
