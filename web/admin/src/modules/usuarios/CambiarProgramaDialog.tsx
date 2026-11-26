import { Button, Group, Modal, Select, Stack, Text } from "@mantine/core";
import { useState } from "react";
import { ApiError } from "../../api/client";
import { useSetConsultaUserUnit } from "../../api/consultaUsers";
import type { ConsultaUser, UnitNode } from "../../api/types";
import { Notice } from "../../components/Notice";

const SIN_PROGRAMA = "__ninguno__";

/** Las opciones del desplegable: los programas del alcance y, solo con alcance global, ninguno. */
export function opcionesDePrograma(units: Pick<UnitNode, "id" | "name">[], isGlobal: boolean) {
  return [
    ...(isGlobal ? [{ value: SIN_PROGRAMA, label: "Ninguno (global)" }] : []),
    ...units.map((u) => ({ value: u.id, label: u.name })),
  ];
}

/** Cambiar el programa de un usuario de la Consulta (feature 023). */
export function CambiarProgramaDialog({
  user,
  units,
  isGlobal,
  onClose,
}: {
  user: ConsultaUser;
  units: UnitNode[];
  isGlobal: boolean;
  onClose: () => void;
}) {
  const update = useSetConsultaUserUnit();
  const actual = user.unit?.id ?? SIN_PROGRAMA;
  const [unit, setUnit] = useState<string>(actual);
  const [error, setError] = useState<string | null>(null);

  async function guardar() {
    setError(null);
    try {
      await update.mutateAsync({ id: user.id, unit_id: unit === SIN_PROGRAMA ? null : unit });
      onClose();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "No se pudo cambiar el programa.");
    }
  }

  return (
    <Modal opened onClose={onClose} centered title={`Cambiar el programa de ${user.username}`}>
      <Stack gap="md">
        <Text c="dimmed" fz="sm">
          El programa decide qué cuentas de administración gestionan a esta persona. No cambia lo que puede consultar, su
          contraseña ni sus conversaciones.
        </Text>
        <Select
          label="Programa"
          data={opcionesDePrograma(units, isGlobal)}
          value={unit}
          onChange={(value) => value && setUnit(value)}
          allowDeselect={false}
        />
        {error && <Notice tone="danger">{error}</Notice>}
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose} disabled={update.isPending}>
            Cancelar
          </Button>
          <Button onClick={() => void guardar()} disabled={unit === actual} loading={update.isPending}>
            Guardar
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}
