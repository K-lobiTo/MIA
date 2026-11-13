import { Button, Group, MultiSelect, Pagination, Paper, Select, Text } from "@mantine/core";
import { IconDownload, IconTrash } from "@tabler/icons-react";
import { useState } from "react";
import { PAGE_SIZE, downloadContactsCsv, useContacts } from "../../api/contacts";
import { useBots } from "../../api/bots";
import type { Contact, ContactStatus } from "../../api/types";
import { capabilities } from "../../auth/capabilities";
import { useMe } from "../../auth/session";
import { Notice } from "../../components/Notice";
import { BorrarContactosDialog, type DeleteTarget } from "./BorrarContactosDialog";
import { ContactTable } from "./ContactTable";
import {
  EMPTY_FORM,
  NO_FILTER,
  PERSONAL_DATA_NOTE,
  STATUS_LABEL,
  STATUS_ORDER,
  hasFilters,
  pageCount,
  toFilters,
  type EmailFilter,
  type FiltersForm,
} from "./contactosUtils";
import "./contactos.css";

const EMAIL_OPTIONS = [
  { value: NO_FILTER, label: "Con o sin correo" },
  { value: "con", label: "Solo con correo" },
  { value: "sin", label: "Solo sin correo" },
];

/** Módulo "Contactos de WhatsApp" (feature 017): quienes escribieron al bot, con su teléfono y, si los dejaron, su nombre y
 * su correo. Lista, filtra, descarga en CSV y borra. Solo el alcance global lo usa (la API hace cumplir el permiso). */
export function ContactosPage() {
  const canManage = capabilities(useMe()).canManageContacts;
  const [form, setForm] = useState<FiltersForm>(EMPTY_FORM);
  const [page, setPage] = useState(1);
  const [dialog, setDialog] = useState<DeleteTarget | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);
  const filters = toFilters(form);
  const contacts = useContacts(filters, page, canManage);
  const bots = useBots(canManage);
  const data = contacts.data;

  function change(next: Partial<FiltersForm>) {
    setForm({ ...form, ...next });
    setPage(1);
    setMessage(null);
  }

  async function download() {
    setDownloadError(null);
    setDownloading(true);
    try {
      await downloadContactsCsv(filters);
    } catch (caught) {
      setDownloadError(caught instanceof Error ? caught.message : "No se pudo descargar el archivo.");
    } finally {
      setDownloading(false);
    }
  }

  function askDelete(contact: Contact) {
    setMessage(null);
    setDialog({ kind: "one", contact });
  }

  const total = data?.total ?? 0;
  const botOptions = [
    { value: NO_FILTER, label: "Todos los bots" },
    ...(bots.data?.bots ?? []).map((bot) => ({ value: bot.id, label: bot.name })),
  ];
  const statusOptions = STATUS_ORDER.map((status) => ({ value: status, label: STATUS_LABEL[status].text }));

  return (
    <>
      <h1>Contactos de WhatsApp</h1>
      <Text c="dimmed">
        Las personas que escribieron al bot de WhatsApp: su teléfono y, si quisieron dejarlos, su nombre y su correo, para que la
        Coordinación del programa pueda contactarlas. Dejar los datos es opcional para la persona.
      </Text>
      {!canManage && <Notice tone="info">Solo el alcance global puede ver los contactos de WhatsApp.</Notice>}
      {canManage && <Notice tone="warn">{PERSONAL_DATA_NOTE}</Notice>}
      {message && <Notice tone="ok">{message}</Notice>}
      {downloadError && <Notice tone="danger">{downloadError}</Notice>}
      {canManage && contacts.isPending && <Text c="dimmed">Cargando contactos...</Text>}
      {canManage && contacts.isError && (
        <Notice tone="danger">
          No se pudieron cargar los contactos: {contacts.error.message}{" "}
          <Button variant="default" size="compact-sm" onClick={() => contacts.refetch()}>
            Reintentar
          </Button>
        </Notice>
      )}

      {canManage && data && (
        <>
          <div className="contactos-summary" aria-label="Contactos por estado">
            {STATUS_ORDER.map((status) => (
              <Paper key={status} withBorder p="sm" radius="md">
                <Text fz="xs" c="dimmed">
                  {STATUS_LABEL[status].text}
                </Text>
                <Text fz="xl" fw={700} className="contactos-count">
                  {data.summary[status as ContactStatus]}
                </Text>
              </Paper>
            ))}
          </div>

          <div className="contactos-filters">
            <Select
              label="Bot"
              data={botOptions}
              value={form.botId}
              onChange={(value) => change({ botId: value ?? NO_FILTER })}
              allowDeselect={false}
            />
            <MultiSelect
              label="Estado"
              placeholder={form.statuses.length === 0 ? "Todos los estados" : undefined}
              data={statusOptions}
              value={form.statuses}
              onChange={(value) => change({ statuses: value as ContactStatus[] })}
              clearable
            />
            <Select
              label="Correo"
              data={EMAIL_OPTIONS}
              value={form.email}
              onChange={(value) => change({ email: (value ?? NO_FILTER) as EmailFilter })}
              allowDeselect={false}
            />
          </div>

          <Group justify="space-between" align="center" gap="sm">
            <Text>
              <strong>{total}</strong> {total === 1 ? "contacto" : "contactos"}
              {hasFilters(form) ? " con estos filtros" : ""}
            </Text>
            <Group gap="sm">
              <Button
                variant="default"
                leftSection={<IconDownload size={16} />}
                onClick={() => void download()}
                loading={downloading}
                disabled={total === 0}
              >
                Descargar CSV
              </Button>
              <Button
                color="coral"
                variant="light"
                leftSection={<IconTrash size={16} />}
                onClick={() => setDialog({ kind: "filtered", count: total, filters, filtered: hasFilters(form) })}
                disabled={total === 0}
              >
                {hasFilters(form) ? `Borrar los ${total} filtrados` : `Borrar los ${total}`}
              </Button>
            </Group>
          </Group>

          {data.items.length > 0 ? (
            <ContactTable contacts={data.items} onDelete={askDelete} />
          ) : (
            <Text c="dimmed">
              {hasFilters(form) ? "Ningún contacto cumple estos filtros." : "Todavía no hay contactos. Aparecen cuando alguien escribe al bot con la función de contacto encendida."}
            </Text>
          )}
          {pageCount(total, PAGE_SIZE) > 1 && (
            <Pagination total={pageCount(total, PAGE_SIZE)} value={page} onChange={setPage} />
          )}
        </>
      )}

      {dialog && (
        <BorrarContactosDialog
          target={dialog}
          onClose={() => setDialog(null)}
          onDeleted={(count) => {
            setMessage(count === 1 ? "Se borró 1 contacto." : `Se borraron ${count} contactos.`);
            setPage(1);
          }}
        />
      )}
    </>
  );
}
