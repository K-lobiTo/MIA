import { ActionIcon, Table } from "@mantine/core";
import { IconTrash } from "@tabler/icons-react";
import type { Contact } from "../../api/types";
import { StatusBadge } from "../../components/StatusBadge";
import { STATUS_LABEL, formatDate, formatPhone } from "./contactosUtils";

interface Props {
  contacts: Contact[];
  onDelete: (contact: Contact) => void;
}

/** La lista de contactos, de la más reciente a la más antigua, con la acción de borrar por fila. */
export function ContactTable({ contacts, onDelete }: Props) {
  return (
    <Table.ScrollContainer minWidth={760}>
      <Table highlightOnHover verticalSpacing="xs" aria-label="Contactos de WhatsApp">
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Teléfono</Table.Th>
            <Table.Th>Bot</Table.Th>
            <Table.Th>Nombre</Table.Th>
            <Table.Th>Correo</Table.Th>
            <Table.Th>Estado</Table.Th>
            <Table.Th>Primer mensaje</Table.Th>
            <Table.Th>Último mensaje</Table.Th>
            <Table.Th>
              <span className="contactos-sr">Acciones</span>
            </Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {contacts.map((contact) => {
            const status = STATUS_LABEL[contact.status];
            return (
              <Table.Tr key={contact.id}>
                <Table.Td className="contactos-phone">{formatPhone(contact.phone)}</Table.Td>
                <Table.Td>{contact.bot.name}</Table.Td>
                <Table.Td>{contact.name ?? <span className="contactos-empty">sin nombre</span>}</Table.Td>
                <Table.Td className="contactos-wrap">{contact.email ?? <span className="contactos-empty">sin correo</span>}</Table.Td>
                <Table.Td>
                  <StatusBadge tone={status.tone}>{status.text}</StatusBadge>
                </Table.Td>
                <Table.Td>{formatDate(contact.created_at)}</Table.Td>
                <Table.Td>{formatDate(contact.last_seen_at)}</Table.Td>
                <Table.Td>
                  <ActionIcon
                    variant="subtle"
                    color="coral"
                    aria-label={`Borrar el contacto ${formatPhone(contact.phone)}`}
                    onClick={() => onDelete(contact)}
                  >
                    <IconTrash size={16} />
                  </ActionIcon>
                </Table.Td>
              </Table.Tr>
            );
          })}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  );
}
