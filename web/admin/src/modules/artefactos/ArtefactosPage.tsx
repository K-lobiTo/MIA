import { Button, Group, Modal, Text } from "@mantine/core";
import { IconPlus } from "@tabler/icons-react";
import { useState } from "react";
import { useRegenerateKey, useArtifacts, useUpdateArtifact } from "../../api/artifacts";
import { useInventory } from "../../api/inventory";
import type { Artifact } from "../../api/types";
import { Notice } from "../../components/Notice";
import { ArtifactCard } from "./ArtifactCard";
import { ArtifactForm } from "./ArtifactForm";
import { capabilities } from "../../auth/capabilities";
import { useMe } from "../../auth/session";
import { formatUsd } from "./capMath";
import { KeyReveal } from "./KeyReveal";
import "./artefactos.css";

type DialogState =
  | { kind: "new" }
  | { kind: "edit"; artifact: Artifact }
  | { kind: "reveal"; name: string; key: string; regenerated: boolean }
  | { kind: "confirm-regenerate"; artifact: Artifact };

export function ArtefactosPage() {
  const canSeeGlobal = capabilities(useMe()).showGlobalCaps;
  const artifacts = useArtifacts(true);
  const inventory = useInventory();
  const update = useUpdateArtifact();
  const regenerate = useRegenerateKey();
  const [dialog, setDialog] = useState<DialogState | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const units = inventory.data?.units ?? [];
  const modes = artifacts.data?.modes ?? [];
  const close = () => setDialog(null);

  async function toggleActive(artifact: Artifact) {
    setActionError(null);
    try {
      await update.mutateAsync({ id: artifact.id, changes: { active: !artifact.active } });
    } catch (caught) {
      setActionError(caught instanceof Error ? caught.message : "No se pudo cambiar el estado.");
    }
  }

  async function confirmRegenerate(artifact: Artifact) {
    setActionError(null);
    try {
      const result = await regenerate.mutateAsync(artifact.id);
      setDialog({ kind: "reveal", name: artifact.name, key: result.key, regenerated: true });
    } catch (caught) {
      setDialog(null);
      setActionError(caught instanceof Error ? caught.message : "No se pudo regenerar la clave.");
    }
  }

  return (
    <>
      <Group justify="space-between" align="center" gap="md">
        <h1>Artefactos y accesos</h1>
        <Button leftSection={<IconPlus size={16} />} onClick={() => setDialog({ kind: "new" })}>
          Nuevo artefacto
        </Button>
      </Group>
      <Text c="dimmed">
        Cada artefacto tiene su propia clave y solo puede consultar los dominios y usar los modos que se le permitan aquí.
        Los cambios rigen desde la consulta siguiente.
      </Text>

      {artifacts.data?.global && canSeeGlobal && (
        <Notice tone="info">
          <strong>Tope diario de toda la API:</strong> {formatUsd(artifacts.data.global.daily_cap_usd)}. Hoy se han gastado{" "}
          {formatUsd(artifacts.data.global.spent_today_usd)}. Este tope se fija en la configuración de la instancia y no se
          cambia desde el panel.
        </Notice>
      )}
      {artifacts.data?.global?.caps_exceed_global && canSeeGlobal && (
        <Notice tone="warn">
          <strong>Los topes de los artefactos suman {formatUsd(artifacts.data.global.sum_of_artifact_caps_usd)}</strong>, más que
          el tope de toda la API. Un artefacto puede quedarse sin servicio por el gasto de otros aunque no haya alcanzado el
          suyo: baja algún tope, o sube el de la API en la configuración de la instancia.
        </Notice>
      )}
      {actionError && <Notice tone="danger">{actionError}</Notice>}
      {artifacts.isPending && <Text c="dimmed">Cargando artefactos...</Text>}
      {artifacts.isError && (
        <Notice tone="danger">
          No se pudieron cargar los artefactos: {artifacts.error.message}{" "}
          <Button variant="default" size="compact-sm" onClick={() => artifacts.refetch()}>
            Reintentar
          </Button>
        </Notice>
      )}

      {artifacts.data && (
        <div className="art-list">
          {artifacts.data.artifacts.map((artifact) => (
            <ArtifactCard
              key={artifact.id}
              artifact={artifact}
              units={units}
              busy={update.isPending || regenerate.isPending}
              onEdit={() => setDialog({ kind: "edit", artifact })}
              onRegenerate={() => setDialog({ kind: "confirm-regenerate", artifact })}
              onToggleActive={() => void toggleActive(artifact)}
            />
          ))}
          {artifacts.data.artifacts.length === 0 && (
            <Text c="dimmed">Todavía no hay artefactos registrados. Registra el primero con "Nuevo artefacto".</Text>
          )}
        </div>
      )}

      {dialog?.kind === "new" && (
        <ArtifactForm
          units={units}
          modes={modes}
          onClose={close}
          onCreated={(created) => setDialog({ kind: "reveal", name: created.name, key: created.key, regenerated: false })}
        />
      )}
      {dialog?.kind === "edit" && <ArtifactForm artifact={dialog.artifact} units={units} modes={modes} onClose={close} />}
      {dialog?.kind === "reveal" && (
        <KeyReveal artifactName={dialog.name} keyValue={dialog.key} regenerated={dialog.regenerated} onClose={close} />
      )}
      {dialog?.kind === "confirm-regenerate" && (
        <Modal opened onClose={close} title="Regenerar clave" centered>
          <Text>
            La clave actual de <strong>{dialog.artifact.name}</strong> dejará de funcionar de inmediato, y todo lo que la use
            (el sitio publicado, scripts) tendrá que actualizarse con la nueva.
          </Text>
          <Group justify="flex-end" mt="md">
            <Button variant="default" onClick={close}>
              Cancelar
            </Button>
            <Button color="coral" onClick={() => void confirmRegenerate(dialog.artifact)}>
              Regenerar
            </Button>
          </Group>
        </Modal>
      )}
    </>
  );
}
