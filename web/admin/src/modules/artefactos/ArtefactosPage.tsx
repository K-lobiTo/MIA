import { useState } from "react";
import { useOutletContext } from "react-router-dom";
import { useRegenerateKey, useArtifacts, useUpdateArtifact } from "../../api/artifacts";
import { useAdminKey } from "../../api/client";
import { useInventory } from "../../api/inventory";
import type { Artifact } from "../../api/types";
import { ArtifactCard } from "./ArtifactCard";
import { ArtifactForm } from "./ArtifactForm";
import { formatUsd } from "./capMath";
import { KeyReveal } from "./KeyReveal";
import "./artefactos.css";

type DialogState =
  | { kind: "new" }
  | { kind: "edit"; artifact: Artifact }
  | { kind: "reveal"; name: string; key: string; regenerated: boolean }
  | { kind: "confirm-regenerate"; artifact: Artifact };

export function ArtefactosPage() {
  const adminKey = useAdminKey();
  const { askForKey } = useOutletContext<{ askForKey: () => void }>();
  const artifacts = useArtifacts(Boolean(adminKey));
  const inventory = useInventory();
  const update = useUpdateArtifact();
  const regenerate = useRegenerateKey();
  const [dialog, setDialog] = useState<DialogState | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  if (!adminKey) {
    return (
      <>
        <h1>Artefactos y accesos</h1>
        <div className="notice notice-admin">
          Este módulo necesita la clave de administración.{" "}
          <button className="btn btn-small btn-primary" onClick={askForKey}>
            Ingresar clave
          </button>
        </div>
      </>
    );
  }

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
      <div className="inv-toolbar">
        <h1>Artefactos y accesos</h1>
        <button className="btn btn-primary" onClick={() => setDialog({ kind: "new" })}>
          + Nuevo artefacto
        </button>
      </div>
      <p className="muted">
        Cada artefacto tiene su propia clave y solo puede consultar los dominios y usar los modos que se le permitan aquí.
        Los cambios rigen desde la consulta siguiente.
      </p>

      {artifacts.data && (
        <div className="notice" role="status">
          <strong>Tope diario de toda la API:</strong> {formatUsd(artifacts.data.global.daily_cap_usd)}. Hoy se han gastado{" "}
          {formatUsd(artifacts.data.global.spent_today_usd)}. Este tope se fija en la configuración de la instancia y no se
          cambia desde el panel.
        </div>
      )}
      {artifacts.data?.global.caps_exceed_global && (
        <div className="notice notice-warn" role="alert">
          <strong>Los topes de los artefactos suman {formatUsd(artifacts.data.global.sum_of_artifact_caps_usd)}</strong>, más que
          el tope de toda la API. Un artefacto puede quedarse sin servicio por el gasto de otros aunque no haya alcanzado el
          suyo: baja algún tope, o sube el de la API en la configuración de la instancia.
        </div>
      )}
      {actionError && (
        <div className="notice notice-danger" role="alert">
          {actionError}
        </div>
      )}
      {artifacts.isPending && <p className="muted">Cargando artefactos...</p>}
      {artifacts.isError && (
        <div className="notice notice-danger" role="alert">
          No se pudieron cargar los artefactos: {artifacts.error.message}{" "}
          <button className="btn btn-small" onClick={() => artifacts.refetch()}>
            Reintentar
          </button>
        </div>
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
            <p className="muted">Todavía no hay artefactos registrados. Registra el primero con "+ Nuevo artefacto".</p>
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
        <div className="overlay" role="dialog" aria-modal="true" aria-label="Regenerar clave">
          <div className="dialog">
            <h2>Regenerar clave</h2>
            <p>
              La clave actual de <strong>{dialog.artifact.name}</strong> dejará de funcionar de inmediato, y todo lo que la use
              (el sitio publicado, scripts) tendrá que actualizarse con la nueva.
            </p>
            <div className="dialog-actions">
              <button className="btn" onClick={close}>
                Cancelar
              </button>
              <button className="btn btn-danger" onClick={() => void confirmRegenerate(dialog.artifact)}>
                Regenerar
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
