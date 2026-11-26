import { Button, Group, List, Modal, Stack, Text } from "@mantine/core";
import { useState } from "react";
import { ApiError } from "../../api/client";
import { useDeleteStructure, useDeletionCheck, type DeletionCheck, type DeletionItem, type StructureKind } from "../../api/structure";
import { Notice } from "../../components/Notice";

const TIPO: Record<StructureKind, string> = { unit: "programa", domain: "dominio" };

const NOMBRES: Record<string, [string, string]> = {
  documents: ["documento", "documentos"],
  folders: ["carpeta", "carpetas"],
  domains: ["dominio", "dominios"],
  consulta_users: ["usuario de la Consulta", "usuarios de la Consulta"],
  admins: ["cuenta de administración", "cuentas de administración"],
  artifacts: ["artefacto", "artefactos"],
  empty_artifacts: ["artefacto", "artefactos"],
  bots: ["bot de WhatsApp", "bots de WhatsApp"],
};

/** "3 documentos", y los nombres si los hay; los que no se pueden nombrar (fuera del alcance) o no caben se cuentan. */
export function describirElemento(item: DeletionItem): string {
  const [uno, varios] = NOMBRES[item.kind] ?? ["elemento", "elementos"];
  const cantidad = `${item.count} ${item.count === 1 ? uno : varios}`;
  // Documentos y carpetas se informan solo por cantidad.
  if (item.kind === "documents" || item.kind === "folders") return cantidad;
  const resto = item.count - item.names.length;
  if (item.names.length === 0) return `${cantidad} (fuera de lo que administras)`;
  return `${cantidad}: ${item.names.join(", ")}${resto > 0 ? ` y ${resto} más` : ""}`;
}

function Lista({ items }: { items: DeletionItem[] }) {
  return (
    <List spacing="xs">
      {items.map((item) => (
        <List.Item key={item.kind}>
          <Text span fw={600}>
            {describirElemento(item)}
          </Text>
          <Text fz="sm" c="dimmed">
            {item.hint}
          </Text>
        </List.Item>
      ))}
    </List>
  );
}

export function EliminarEstructuraContenido({ tipo, check }: { tipo: StructureKind; check: DeletionCheck }) {
  if (!check.can_delete) {
    return (
      <Stack gap="sm">
        <Text>
          El {TIPO[tipo]} <strong>{check.name}</strong> todavía tiene:
        </Text>
        <Lista items={check.blockers} />
      </Stack>
    );
  }
  return (
    <Stack gap="sm">
      <Text>
        ¿Eliminar el {TIPO[tipo]} <strong>{check.name}</strong>?
      </Text>
      {check.affects.length > 0 && (
        <>
          <Text>Esto afecta a:</Text>
          <Lista items={check.affects} />
        </>
      )}
      <Text fw={600}>No se puede deshacer.</Text>
    </Stack>
  );
}

/** Confirmación de eliminar un programa o un dominio: primero pregunta a la API qué pasaría. */
export function EliminarEstructuraDialog({
  tipo,
  id,
  nombre,
  onClose,
}: {
  tipo: StructureKind;
  id: string;
  nombre: string;
  onClose: () => void;
}) {
  const check = useDeletionCheck(tipo, id);
  const remove = useDeleteStructure();
  const [error, setError] = useState<string | null>(null);
  const bloqueado = check.data !== undefined && !check.data.can_delete;

  async function confirmar() {
    setError(null);
    try {
      await remove.mutateAsync({ kind: tipo, id });
      onClose();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : `No se pudo eliminar el ${TIPO[tipo]}.`);
      // Si algo cambió mientras tanto, la ventana lo muestra.
      void check.refetch();
    }
  }

  return (
    <Modal opened onClose={onClose} centered title={bloqueado ? "No se puede eliminar todavía" : `Eliminar ${TIPO[tipo]}`}>
      <Stack gap="md">
        {check.isPending && <Text c="dimmed">Comprobando {nombre}...</Text>}
        {check.isError && <Notice tone="danger">No se pudo comprobar: {check.error.message}</Notice>}
        {check.data && <EliminarEstructuraContenido tipo={tipo} check={check.data} />}
        {error && <Notice tone="danger">{error}</Notice>}
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose} disabled={remove.isPending}>
            {bloqueado ? "Cerrar" : "Cancelar"}
          </Button>
          {check.data?.can_delete && (
            <Button color="coral" onClick={() => void confirmar()} loading={remove.isPending}>
              Eliminar
            </Button>
          )}
        </Group>
      </Stack>
    </Modal>
  );
}
