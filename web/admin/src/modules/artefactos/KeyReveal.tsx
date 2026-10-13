import { Button, Group, Modal } from "@mantine/core";
import { useState } from "react";
import { Notice } from "../../components/Notice";

interface Props {
  artifactName: string;
  keyValue: string;
  regenerated?: boolean;
  onClose: () => void;
}

/** Muestra la clave completa una sola vez (ART-2): después de cerrar este diálogo solo se verá su comienzo. */
export function KeyReveal({ artifactName, keyValue, regenerated, onClose }: Props) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(keyValue);
      setCopied(true);
    } catch {
      // Sin permiso para el portapapeles: la clave está seleccionable en el cuadro de arriba.
      setCopied(false);
    }
  }

  return (
    // Solo se cierra con "Ya la guardé": un clic o Escape por accidente perdería la única vista de la clave.
    <Modal
      opened
      onClose={onClose}
      size="lg"
      centered
      withCloseButton={false}
      closeOnClickOutside={false}
      closeOnEscape={false}
      title={`${regenerated ? "Clave regenerada" : "Artefacto registrado"}: ${artifactName}`}
    >
      <Notice tone="warn">
        <strong>Copia la clave ahora.</strong> No se volverá a mostrar completa: si se pierde, hay que regenerarla.
        {regenerated && " La clave anterior ya dejó de funcionar."}
      </Notice>
      <div className="key-box" data-testid="clave-completa">
        {keyValue}
      </div>
      <Group justify="space-between" mt="md">
        <Button variant="default" onClick={copy}>
          {copied ? "Copiada" : "Copiar clave"}
        </Button>
        <Button onClick={onClose}>Ya la guardé</Button>
      </Group>
    </Modal>
  );
}
