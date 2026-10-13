import { Button, Group, Modal, Stack, Text } from "@mantine/core";
import { useState } from "react";
import { ApiError } from "../../../api/client";
import { useCreateDomain, useCreateFolder, useCreateUnit, useDeleteFolder, useRenameFolder } from "../../../api/inventoryMutations";
import { Notice } from "../../../components/Notice";
import { FormDialog } from "../../../components/FormDialog";

interface CloseProps {
  onClose: () => void;
}

export function NewUnitDialog({ onClose }: CloseProps) {
  const create = useCreateUnit();
  return (
    <FormDialog
      title="Nuevo programa"
      intro="Un programa agrupa los dominios de una unidad o área académica (por ejemplo, la Unidad de Postgrados de Computación)."
      submitLabel="Crear programa"
      fields={[
        { name: "name", label: "Nombre", required: true },
        { name: "description", label: "Descripción", multiline: true },
      ]}
      onSubmit={(v) => create.mutateAsync({ name: v.name, description: v.description })}
      onClose={onClose}
    />
  );
}

export function NewDomainDialog({ unitId, unitName, onClose }: CloseProps & { unitId: string; unitName: string }) {
  const create = useCreateDomain();
  return (
    <FormDialog
      title={`Nuevo dominio en ${unitName}`}
      intro="El dominio es lo que se elige al consultar (por ejemplo, Currículum). Su nombre solo debe ser único dentro del programa."
      submitLabel="Crear dominio"
      fields={[
        { name: "name", label: "Nombre", required: true },
        { name: "description", label: "Descripción", multiline: true },
      ]}
      onSubmit={(v) => create.mutateAsync({ unit_id: unitId, name: v.name, description: v.description })}
      onClose={onClose}
      // INV-12: indicar qué artefactos lo verán y cuáles necesitan que se les habilite.
      renderResult={(domain) => (
        <Stack gap="sm">
          <Text>
            Dominio <strong>{domain.name}</strong> creado.
          </Text>
          <Notice tone="info">
            <strong>Lo verán de inmediato:</strong>{" "}
            {domain.visible_to.now.length > 0 ? domain.visible_to.now.join(", ") : "ningún artefacto todavía."}
          </Notice>
          {domain.visible_to.needs_enabling.length > 0 && (
            <Notice tone="warn">
              <strong>Hay que habilitarlo en Artefactos y accesos para:</strong> {domain.visible_to.needs_enabling.join(", ")}.
              Tienen dominios elegidos uno a uno.
            </Notice>
          )}
        </Stack>
      )}
    />
  );
}

export function NewFolderDialog({
  domainId,
  parentId,
  where,
  onClose,
}: CloseProps & { domainId: string; parentId: string | null; where: string }) {
  const create = useCreateFolder();
  return (
    <FormDialog
      title={`Nueva carpeta en ${where}`}
      intro="Las carpetas solo ordenan los documentos: la consulta sigue siendo por dominio."
      submitLabel="Crear carpeta"
      fields={[{ name: "name", label: "Nombre", required: true }]}
      onSubmit={(v) => create.mutateAsync({ domainId, name: v.name, parentId })}
      onClose={onClose}
    />
  );
}

export function RenameFolderDialog({ folderId, currentName, onClose }: CloseProps & { folderId: string; currentName: string }) {
  const rename = useRenameFolder();
  return (
    <FormDialog
      title="Renombrar carpeta"
      submitLabel="Guardar"
      fields={[{ name: "name", label: "Nombre", required: true, initial: currentName }]}
      onSubmit={(v) => rename.mutateAsync({ folderId, name: v.name })}
      onClose={onClose}
    />
  );
}

export function DeleteFolderDialog({ folderId, name, onClose }: CloseProps & { folderId: string; name: string }) {
  const remove = useDeleteFolder();
  const [error, setError] = useState<string | null>(null);

  async function confirm() {
    setError(null);
    try {
      await remove.mutateAsync(folderId);
      onClose();
    } catch (caught) {
      // Una carpeta con contenido se rechaza con un mensaje que explica que debe estar vacía.
      setError(caught instanceof ApiError ? caught.message : "No se pudo borrar la carpeta.");
    }
  }

  return (
    <Modal opened onClose={onClose} title="Borrar carpeta" centered>
      <Stack gap="sm">
        <Text>
          ¿Borrar la carpeta <strong>{name}</strong>? Solo se puede borrar si está vacía.
        </Text>
        {error && <Notice tone="danger">{error}</Notice>}
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            Cancelar
          </Button>
          <Button color="coral" onClick={confirm} loading={remove.isPending}>
            Borrar
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}
