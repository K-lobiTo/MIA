import { ActionIcon, Button, Group, Modal, Paper, Table, Text, Tooltip } from "@mantine/core";
import { IconPencil, IconPlus, IconTrash } from "@tabler/icons-react";
import { useState } from "react";
import { useDeleteEquivalence, useEquivalences } from "../../api/equivalences";
import type { Equivalence } from "../../api/types";
import { Notice } from "../../components/Notice";
import { capabilities } from "../../auth/capabilities";
import { useMe } from "../../auth/session";
import { EquivalenciaForm } from "./EquivalenciaForm";
import { formatWhen } from "./equivalenciasUtils";

type DialogState = { kind: "new" } | { kind: "edit"; equivalence: Equivalence } | { kind: "delete"; equivalence: Equivalence };

/** Lista de siglas y sus formas desarrolladas de la búsqueda híbrida (feature 010). Todas las personas que
 * administran la ven; solo el alcance global la cambia (la API hace cumplir el permiso). */
export function EquivalenciasPage() {
  const canEdit = capabilities(useMe()).canEditEquivalences;
  const equivalences = useEquivalences();
  const remove = useDeleteEquivalence();
  const [dialog, setDialog] = useState<DialogState | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const rows = equivalences.data?.equivalences ?? [];
  const close = () => setDialog(null);

  async function confirmDelete(equivalence: Equivalence) {
    setActionError(null);
    try {
      await remove.mutateAsync(equivalence.id);
      close();
    } catch (caught) {
      close();
      setActionError(caught instanceof Error ? caught.message : "No se pudo borrar la equivalencia.");
    }
  }

  return (
    <>
      <Group justify="space-between" align="center" gap="md">
        <h1>Siglas y equivalencias</h1>
        {canEdit && (
          <Button leftSection={<IconPlus size={16} />} onClick={() => setDialog({ kind: "new" })}>
            Agregar equivalencia
          </Button>
        )}
      </Group>
      <Text c="dimmed">
        Cuando una pregunta lleva una sigla (por ejemplo, TFG), la búsqueda por palabras también busca su forma desarrollada
        (Trabajo Final de Graduación), y al revés. La lista vale para todos los programas y el cambio se nota en menos de un
        minuto, sin reindexar los documentos. Mientras la búsqueda híbrida esté apagada en la instancia, la lista no tiene
        efecto.
      </Text>
      {!canEdit && equivalences.data && (
        <Notice tone="info">Solo el alcance global puede agregar, editar o borrar equivalencias. Aquí puedes verlas.</Notice>
      )}
      {actionError && <Notice tone="danger">{actionError}</Notice>}
      {equivalences.isPending && <Text c="dimmed">Cargando equivalencias...</Text>}
      {equivalences.isError && (
        <Notice tone="danger">
          No se pudieron cargar las equivalencias: {equivalences.error.message}{" "}
          <Button variant="default" size="compact-sm" onClick={() => equivalences.refetch()}>
            Reintentar
          </Button>
        </Notice>
      )}

      {equivalences.data && (
        <Paper component="section" withBorder p="md" radius="md" aria-label="Equivalencias de siglas">
          {rows.length === 0 ? (
            <Text c="dimmed">
              Todavía no hay equivalencias.{canEdit ? ' Agrega la primera con "Agregar equivalencia".' : ""}
            </Text>
          ) : (
            <Table.ScrollContainer minWidth={640}>
              <Table verticalSpacing="sm" highlightOnHover>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th scope="col">Sigla</Table.Th>
                    <Table.Th scope="col">Forma desarrollada</Table.Th>
                    <Table.Th scope="col">Último cambio</Table.Th>
                    {canEdit && (
                      <Table.Th scope="col">
                        <span className="sr-only">Acciones</span>
                      </Table.Th>
                    )}
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {rows.map((row) => (
                    <Table.Tr key={row.id}>
                      <Table.Th scope="row">{row.sigla}</Table.Th>
                      <Table.Td>{row.form}</Table.Td>
                      <Table.Td>
                        {row.updated_by ?? row.created_by}
                        <Text c="dimmed" fz="sm" component="span">
                          {" "}
                          · {formatWhen(row.updated_at ?? row.created_at)}
                        </Text>
                      </Table.Td>
                      {canEdit && (
                        <Table.Td>
                          <Group gap="xs" justify="flex-end" wrap="nowrap">
                            <Tooltip label="Editar">
                              <ActionIcon
                                variant="default"
                                aria-label={`Editar ${row.sigla}`}
                                onClick={() => setDialog({ kind: "edit", equivalence: row })}
                              >
                                <IconPencil size={16} />
                              </ActionIcon>
                            </Tooltip>
                            <Tooltip label="Borrar">
                              <ActionIcon
                                variant="default"
                                aria-label={`Borrar ${row.sigla}`}
                                onClick={() => setDialog({ kind: "delete", equivalence: row })}
                              >
                                <IconTrash size={16} />
                              </ActionIcon>
                            </Tooltip>
                          </Group>
                        </Table.Td>
                      )}
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </Table.ScrollContainer>
          )}
        </Paper>
      )}

      {dialog?.kind === "new" && <EquivalenciaForm existing={rows} onClose={close} />}
      {dialog?.kind === "edit" && <EquivalenciaForm equivalence={dialog.equivalence} existing={rows} onClose={close} />}
      {dialog?.kind === "delete" && (
        <Modal opened onClose={close} title="Borrar equivalencia" centered>
          <Text>
            Al borrar <strong>{dialog.equivalence.sigla}</strong> = <strong>{dialog.equivalence.form}</strong>, la pregunta con
            la sigla dejará de buscar la forma desarrollada, y al revés, en menos de un minuto. Los documentos no se tocan.
          </Text>
          <Group justify="flex-end" mt="md">
            <Button variant="default" onClick={close}>
              Cancelar
            </Button>
            <Button color="coral" loading={remove.isPending} onClick={() => void confirmDelete(dialog.equivalence)}>
              Borrar
            </Button>
          </Group>
        </Modal>
      )}
    </>
  );
}
