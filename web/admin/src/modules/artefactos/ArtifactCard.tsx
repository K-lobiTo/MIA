import type { Artifact, UnitNode } from "../../api/types";
import { describeAccess, describeModes } from "./accessUtils";

interface Props {
  artifact: Artifact;
  units: UnitNode[];
  busy: boolean;
  onEdit: () => void;
  onRegenerate: () => void;
  onToggleActive: () => void;
}

export function ArtifactCard({ artifact, units, busy, onEdit, onRegenerate, onToggleActive }: Props) {
  return (
    <article className="card art-card" aria-label={artifact.name}>
      <div className="art-head">
        <span className="art-name">{artifact.name}</span>
        <span className={artifact.active ? "badge badge-ok" : "badge badge-muted"}>
          {artifact.active ? "Activo" : "Desactivado"}
        </span>
        <span className="art-key" title="Comienzo de su clave">
          {artifact.key_prefix}...
        </span>
        <span className="branch-meta">{artifact.queries_last_7_days} consultas (7 días)</span>
      </div>
      {artifact.description && <p className="muted">{artifact.description}</p>}
      <dl className="art-meta">
        <dt>Dominios</dt>
        <dd>
          {describeAccess(artifact.access, units)}{" "}
          <span className="muted">({artifact.allowed_domain_count} en total)</span>
        </dd>
        <dt>Modos</dt>
        <dd>{describeModes(artifact.modes)}</dd>
      </dl>
      <div className="art-actions">
        <button className="btn btn-small" onClick={onEdit} disabled={busy}>
          Editar
        </button>
        <button className="btn btn-small" onClick={onRegenerate} disabled={busy}>
          Regenerar clave
        </button>
        <button className="btn btn-small" onClick={onToggleActive} disabled={busy}>
          {artifact.active ? "Desactivar" : "Reactivar"}
        </button>
      </div>
    </article>
  );
}
