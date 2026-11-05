import { Button, Group, Modal, Select, Stack, Text, TextInput } from "@mantine/core";
import { useState } from "react";
import { ApiError } from "../../api/client";
import { useCreateConsultaUser } from "../../api/consultaUsers";
import type { ConsultaUserCreated, UnitNode } from "../../api/types";
import { Notice } from "../../components/Notice";
import { MIN_PASSWORD, generatePassword, normalizeUsername, validatePassword, validateUsername } from "./usuariosUtils";

interface Props {
  units: UnitNode[];
  // Solo el alcance global puede crear un usuario sin programa.
  isGlobal: boolean;
  onCreated: (user: ConsultaUserCreated) => void;
  onClose: () => void;
}

const NO_UNIT = "__ninguno__";

/** Registro de un usuario de la Consulta: nombre, programa y contraseña opcional (vacía: la genera el servidor). */
export function UserForm({ units, isGlobal, onCreated, onClose }: Props) {
  const create = useCreateConsultaUser();
  const [username, setUsername] = useState("");
  const [unit, setUnit] = useState<string | null>(isGlobal ? NO_UNIT : (units[0]?.id ?? null));
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const nameProblem = username === "" ? null : validateUsername(username);
  const passwordProblem = validatePassword(password);
  const ready = username.trim() !== "" && nameProblem === null && passwordProblem === null && unit !== null;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!ready || pending) return;
    setPending(true);
    setError(null);
    try {
      const created = await create.mutateAsync({
        username: normalizeUsername(username),
        unit_id: unit === NO_UNIT ? null : unit,
        password: password === "" ? null : password,
      });
      onCreated(created);
    } catch (caught) {
      // Se muestra el motivo (p. ej. un nombre repetido) y se conserva lo escrito.
      setError(caught instanceof ApiError ? caught.message : "No se pudo registrar el usuario.");
    } finally {
      setPending(false);
    }
  }

  const options = [
    ...(isGlobal ? [{ value: NO_UNIT, label: "Ninguno (global)" }] : []),
    ...units.map((u) => ({ value: u.id, label: u.name })),
  ];

  return (
    <Modal opened onClose={onClose} centered closeOnClickOutside={false} title="Registrar usuario">
      <form onSubmit={submit}>
        <Stack gap="md">
          <Text c="dimmed" fz="sm">
            Un usuario de la Consulta inicia sesión con este nombre y su contraseña para guardar sus conversaciones. No tiene
            permisos propios: lo que puede consultar lo decide el artefacto.
          </Text>
          <TextInput
            label="Usuario"
            data-autofocus
            value={username}
            onChange={(e) => setUsername(e.currentTarget.value)}
            error={nameProblem ?? undefined}
            autoComplete="off"
          />
          <Select
            label="Programa"
            description="Decide qué cuentas de administración lo gestionan. No limita lo que puede consultar."
            data={options}
            value={unit}
            onChange={setUnit}
            allowDeselect={false}
          />
          <TextInput
            label="Contraseña inicial (opcional)"
            description={`Déjala vacía para que se genere una. Si la escribes, al menos ${MIN_PASSWORD} caracteres.`}
            value={password}
            onChange={(e) => setPassword(e.currentTarget.value)}
            error={passwordProblem ?? undefined}
            autoComplete="off"
            rightSectionWidth={86}
            rightSection={
              <Button size="compact-xs" variant="subtle" onClick={() => setPassword(generatePassword())}>
                Generar
              </Button>
            }
          />
          {error && <Notice tone="danger">{error}</Notice>}
          <Group justify="flex-end">
            <Button variant="default" onClick={onClose}>
              Cancelar
            </Button>
            <Button type="submit" disabled={!ready} loading={pending}>
              Registrar
            </Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  );
}
