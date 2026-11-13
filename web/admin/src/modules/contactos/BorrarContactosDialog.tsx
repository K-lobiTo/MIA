import { Button, Group, Modal, Stack, Text } from "@mantine/core";
import { useState } from "react";
import { useDeleteContact, useDeleteFilteredContacts, type ContactFilters } from "../../api/contacts";
import type { Contact } from "../../api/types";
import { Notice } from "../../components/Notice";
import { IRREVERSIBLE_NOTE, bulkText, bulkTitle, formatPhone } from "./contactosUtils";

export type DeleteTarget =
  | { kind: "one"; contact: Contact }
  // `count` es el conteo que la persona ve en pantalla: la API borra solo si sigue siendo ese (si cambió, responde 409).
  | { kind: "filtered"; count: number; filters: ContactFilters; filtered: boolean };

interface Props {
  target: DeleteTarget;
  onClose: () => void;
  /** Se llama tras borrar, con cuántos contactos se borraron. */
  onDeleted: (count: number) => void;
}

/** Confirmación del borrado de un contacto o de todos los filtrados: dice qué se borra, que no se puede deshacer y, en el
 * borrado masivo, cuántos son. */
export function BorrarContactosDialog({ target, onClose, onDeleted }: Props) {
  const deleteOne = useDeleteContact();
  const deleteMany = useDeleteFilteredContacts();
  const [error, setError] = useState<string | null>(null);
  const busy = deleteOne.isPending || deleteMany.isPending;

  async function confirm() {
    setError(null);
    try {
      if (target.kind === "one") {
        await deleteOne.mutateAsync(target.contact.id);
        onDeleted(1);
      } else {
        const result = await deleteMany.mutateAsync({ filters: target.filters, expected: target.count });
        onDeleted(result.deleted);
      }
      onClose();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "No se pudo borrar.");
    }
  }

  const title = target.kind === "one" ? "Borrar contacto" : bulkTitle(target.count);
  return (
    <Modal opened onClose={onClose} title={title} centered closeOnClickOutside={false}>
      <Stack gap="sm">
        {target.kind === "one" ? (
          <Text>
            Se borrará el contacto <strong>{formatPhone(target.contact.phone)}</strong>
            {target.contact.name ? ` (${target.contact.name})` : ""}, con su nombre y su correo. Si esa persona escribe de nuevo al
            bot, se le tratará como una persona nueva.
          </Text>
        ) : (
          <Text>{bulkText(target.count, target.filtered)}</Text>
        )}
        <Notice tone="warn">{IRREVERSIBLE_NOTE}</Notice>
        {error && <Notice tone="danger">{error}</Notice>}
        <Group justify="flex-end" mt="xs">
          <Button variant="default" onClick={onClose} disabled={busy}>
            Cancelar
          </Button>
          <Button color="coral" onClick={() => void confirm()} loading={busy}>
            {target.kind === "one" ? "Borrar contacto" : `Borrar ${target.count}`}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}
