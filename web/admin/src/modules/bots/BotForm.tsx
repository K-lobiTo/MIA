import { Button, Group, List, Modal, Select, Stack, Text, TextInput } from "@mantine/core";
import { useState } from "react";
import { useCreateBot, useUpdateBot } from "../../api/bots";
import { ApiError } from "../../api/client";
import type { Artifact, Bot, UnitNode } from "../../api/types";
import { Notice } from "../../components/Notice";
import { PUBLIC_ACCESS_WARNING, domainsOfArtifact, validateNumberId } from "./botsUtils";

interface Props {
  // Con `bot` se edita; sin él se registra uno nuevo.
  bot?: Bot;
  artifacts: Artifact[];
  units: UnitNode[];
  onClose: () => void;
}

/** Registro y edición de un bot. Al asignar o cambiar el artefacto se pide confirmar, con la advertencia de que el bot
 * responde a cualquiera y la lista de dominios que verá (BOT-7). */
export function BotForm({ bot, artifacts, units, onClose }: Props) {
  const create = useCreateBot();
  const update = useUpdateBot();
  const [name, setName] = useState(bot?.name ?? "");
  const [numberId, setNumberId] = useState(bot?.kapso_number_id ?? "");
  const [artifactId, setArtifactId] = useState<string | null>(bot?.artifact?.id ?? null);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const numberProblem = numberId === "" ? null : validateNumberId(numberId);
  const ready = name.trim() !== "" && validateNumberId(numberId) === null && artifactId !== null;
  const artifactChanged = artifactId !== (bot?.artifact?.id ?? null);
  const selected = artifacts.find((a) => a.id === artifactId) ?? null;

  async function save() {
    if (!ready || pending || artifactId === null) return;
    setPending(true);
    setError(null);
    try {
      if (bot) {
        await update.mutateAsync({
          id: bot.id,
          changes: { name: name.trim(), kapso_number_id: numberId.trim(), artifact_id: artifactId },
        });
      } else {
        await create.mutateAsync({ name: name.trim(), kapso_number_id: numberId.trim(), artifact_id: artifactId });
      }
      onClose();
    } catch (caught) {
      // Se muestra el motivo (p. ej. un nombre o un número repetidos) y se conserva lo escrito.
      setConfirming(false);
      setError(caught instanceof ApiError ? caught.message : "No se pudo guardar el bot.");
    } finally {
      setPending(false);
    }
  }

  function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!ready || pending) return;
    if (artifactChanged) setConfirming(true);
    else void save();
  }

  if (confirming && selected) {
    const domains = domainsOfArtifact(selected, units);
    return (
      <Modal opened onClose={onClose} title="Confirmar el artefacto del bot" centered closeOnClickOutside={false}>
        <Stack gap="sm">
          <Notice tone="warn">{PUBLIC_ACCESS_WARNING}</Notice>
          <Text>
            Con el artefacto <strong>{selected.name}</strong> el bot verá:
          </Text>
          {domains.length > 0 ? (
            <List size="sm" spacing={2}>
              {domains.map((domain) => (
                <List.Item key={domain}>{domain}</List.Item>
              ))}
            </List>
          ) : (
            <Text c="dimmed">Ningún dominio.</Text>
          )}
          {error && <Notice tone="danger">{error}</Notice>}
          <Group justify="flex-end" mt="xs">
            <Button variant="default" onClick={() => setConfirming(false)} disabled={pending}>
              Volver
            </Button>
            <Button onClick={() => void save()} loading={pending}>
              Confirmar
            </Button>
          </Group>
        </Stack>
      </Modal>
    );
  }

  return (
    <Modal opened onClose={onClose} centered closeOnClickOutside={false} title={bot ? `Editar ${bot.name}` : "Registrar bot"}>
      <form onSubmit={submit}>
        <Stack gap="md">
          {!bot && (
            <Text c="dimmed" fz="sm">
              Un bot es un número de WhatsApp de Kapso que responde con la información de un artefacto. Cambiar el artefacto
              después cambia, desde el mensaje siguiente, lo que el bot sabe.
            </Text>
          )}
          <TextInput label="Nombre" data-autofocus value={name} onChange={(e) => setName(e.currentTarget.value)} />
          <TextInput
            label="Identificador del número de Kapso"
            description="El phone_number_id de Kapso. No es el teléfono de nadie."
            value={numberId}
            onChange={(e) => setNumberId(e.currentTarget.value)}
            error={numberProblem ?? undefined}
          />
          <Select
            label="Artefacto asignado"
            description="Sus dominios, su tope diario y su estado son los del bot."
            placeholder="Elige un artefacto"
            data={artifacts.map((a) => ({ value: a.id, label: a.active ? a.name : `${a.name} (desactivado)` }))}
            value={artifactId}
            onChange={setArtifactId}
            allowDeselect={false}
            searchable
          />
          {error && <Notice tone="danger">{error}</Notice>}
          <Group justify="flex-end">
            <Button variant="default" onClick={onClose}>
              Cancelar
            </Button>
            <Button type="submit" disabled={!ready} loading={pending}>
              {artifactChanged ? "Continuar" : "Guardar cambios"}
            </Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  );
}
