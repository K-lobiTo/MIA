import { useState } from "react";
import { ApiError } from "../../api/client";
import { useCreateArtifact, useUpdateArtifact } from "../../api/artifacts";
import type { Artifact, ArtifactCreated, ModeId, ModeInfo, UnitNode } from "../../api/types";
import { MODE_LABEL, describeCost, pruneCoveredDomains } from "./accessUtils";
import { approxQueries, parseUsd, validateCaps } from "./capMath";

interface Props {
  // Con `artifact` se edita; sin él se crea uno nuevo (y el nombre es obligatorio).
  artifact?: Artifact;
  units: UnitNode[];
  modes: ModeInfo[];
  onClose: () => void;
  onCreated?: (artifact: ArtifactCreated) => void;
}

const ALL_MODES: ModeId[] = ["literal", "razonamiento"];
// Tope diario con el que arranca un artefacto nuevo: bajo, para que un error o un abuso cueste poco (ART-8).
const DEFAULT_CAP = "0.50";

export function ArtifactForm({ artifact, units, modes, onClose, onCreated }: Props) {
  const create = useCreateArtifact();
  const update = useUpdateArtifact();
  const [name, setName] = useState(artifact?.name ?? "");
  const [description, setDescription] = useState(artifact?.description ?? "");
  const [allDomains, setAllDomains] = useState(artifact?.access.all_domains ?? false);
  const [unitIds, setUnitIds] = useState<string[]>(artifact?.access.unit_ids ?? []);
  const [domainIds, setDomainIds] = useState<string[]>(artifact?.access.domain_ids ?? []);
  const [selectedModes, setSelectedModes] = useState<ModeId[]>(artifact?.modes ?? ["literal"]);
  const [dailyCap, setDailyCap] = useState(artifact ? String(artifact.daily_cap_usd) : DEFAULT_CAP);
  const [reasoningCap, setReasoningCap] = useState(
    artifact?.reasoning_daily_cap_usd != null ? String(artifact.reasoning_daily_cap_usd) : "",
  );
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const hasAccess = allDomains || unitIds.length > 0 || domainIds.length > 0;
  const capProblem = validateCaps(dailyCap, reasoningCap);
  const ready = (artifact ? true : name.trim() !== "") && hasAccess && selectedModes.length > 0 && capProblem === null;
  const dailyValue = parseUsd(dailyCap);

  function toggle<T>(list: T[], item: T): T[] {
    return list.includes(item) ? list.filter((x) => x !== item) : [...list, item];
  }

  function toggleUnit(id: string) {
    const next = toggle(unitIds, id);
    setUnitIds(next);
    // Los dominios de una unidad completa ya están cubiertos: no se guardan aparte.
    setDomainIds(pruneCoveredDomains(next, domainIds, units));
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!ready || pending) return;
    setPending(true);
    setError(null);
    const access = { all_domains: allDomains, unit_ids: allDomains ? [] : unitIds, domain_ids: allDomains ? [] : domainIds };
    // Se conserva el orden fijo de los modos, sin importar el orden en que se marcaron.
    const orderedModes = ALL_MODES.filter((m) => selectedModes.includes(m));
    const caps = {
      daily_cap_usd: parseUsd(dailyCap)!,
      reasoning_daily_cap_usd: reasoningCap.trim() === "" ? null : parseUsd(reasoningCap),
    };
    try {
      if (artifact) {
        await update.mutateAsync({ id: artifact.id, changes: { description, access, modes: orderedModes, ...caps } });
        onClose();
      } else {
        const created = await create.mutateAsync({ name: name.trim(), description, access, modes: orderedModes, ...caps });
        onCreated?.(created);
      }
    } catch (caught) {
      // Se muestra el motivo (p. ej. un nombre repetido) y se conserva lo escrito.
      setError(caught instanceof ApiError ? caught.message : "No se pudo guardar el artefacto.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="overlay" role="dialog" aria-modal="true" aria-label={artifact ? "Editar artefacto" : "Nuevo artefacto"}>
      <form className="dialog dialog-wide" onSubmit={submit}>
        <h2>{artifact ? `Editar ${artifact.name}` : "Nuevo artefacto"}</h2>
        {!artifact && (
          <p className="muted" style={{ marginBottom: 12 }}>
            Un artefacto es una aplicación que consulta a MIA. Al registrarlo se genera su clave, que se muestra una sola vez.
          </p>
        )}

        {!artifact && (
          <div className="field">
            <label htmlFor="art-nombre">Nombre</label>
            <input id="art-nombre" autoFocus value={name} onChange={(e) => setName(e.target.value)} />
          </div>
        )}
        <div className="field">
          <label htmlFor="art-desc">Descripción</label>
          <textarea id="art-desc" rows={2} value={description} onChange={(e) => setDescription(e.target.value)} />
        </div>

        <fieldset>
          <legend>Información que puede consultar</legend>
          <label className="choice">
            <input type="checkbox" checked={allDomains} onChange={(e) => setAllDomains(e.target.checked)} />
            <span>
              <strong>Todos los dominios</strong>
              <span className="mode-cost">Incluye los de unidades que se creen después.</span>
            </span>
          </label>
          {!allDomains &&
            units.map((unit) => {
              const unitChecked = unitIds.includes(unit.id);
              return (
                <div className="unit-group" key={unit.id}>
                  <label className="choice">
                    <input type="checkbox" checked={unitChecked} onChange={() => toggleUnit(unit.id)} />
                    <span>
                      <strong>Unidad {unit.name} completa</strong>
                      <span className="mode-cost">Incluye los dominios que se creen después en esta unidad.</span>
                    </span>
                  </label>
                  <div className="domains">
                    {unit.domains.map((domain) => (
                      <label className="choice" key={domain.id}>
                        <input
                          type="checkbox"
                          disabled={unitChecked}
                          checked={unitChecked || domainIds.includes(domain.id)}
                          onChange={() => setDomainIds(toggle(domainIds, domain.id))}
                        />
                        <span>{domain.name}</span>
                      </label>
                    ))}
                  </div>
                </div>
              );
            })}
          {!hasAccess && <p className="hint">Elige al menos un dominio o unidad.</p>}
        </fieldset>

        <fieldset>
          <legend>Modos de respuesta que puede usar</legend>
          {ALL_MODES.map((mode) => {
            const info = modes.find((m) => m.id === mode);
            return (
              <label className="choice" key={mode}>
                <input
                  type="checkbox"
                  checked={selectedModes.includes(mode)}
                  onChange={() => setSelectedModes(toggle(selectedModes, mode))}
                />
                <span>
                  <strong>{MODE_LABEL[mode]}</strong>
                  <span className="mode-cost">
                    {describeCost(info?.avg_cost_usd_7d)}
                    {info && !info.available && " · todavía no está configurado en esta instancia"}
                  </span>
                </span>
              </label>
            );
          })}
          {selectedModes.length === 0 && <p className="hint">Elige al menos un modo.</p>}
        </fieldset>

        <fieldset>
          <legend>Tope de gasto diario</legend>
          <div className="field">
            <label htmlFor="art-tope">Tope total, para todos los modos (USD por día)</label>
            <input id="art-tope" inputMode="decimal" value={dailyCap} onChange={(e) => setDailyCap(e.target.value)} />
            {dailyValue !== null && (
              <span className="hint">
                {selectedModes
                  .map((mode) => {
                    const approx = approxQueries(dailyValue, modes.find((m) => m.id === mode)?.avg_cost_usd_7d);
                    return approx === null ? null : `unas ${approx} consultas ${mode === "literal" ? "literales" : "con razonamiento"}`;
                  })
                  .filter(Boolean)
                  .join(" o ") || "sin consultas recientes para estimar cuántas alcanza"}
                {" al día (según el costo medio de los últimos 7 días)."}
              </span>
            )}
          </div>
          <div className="field">
            <label htmlFor="art-tope-raz">Tope menor solo para el modo con razonamiento (opcional)</label>
            <input
              id="art-tope-raz"
              inputMode="decimal"
              placeholder="Sin tope propio"
              value={reasoningCap}
              onChange={(e) => setReasoningCap(e.target.value)}
            />
            <span className="hint">Al alcanzarlo, el artefacto sigue respondiendo en los otros modos hasta el tope total.</span>
          </div>
          {capProblem && <p className="hint" role="alert">{capProblem}</p>}
          <p className="hint">Al alcanzar un tope el artefacto deja de responder hasta la medianoche (hora de Costa Rica), sin afectar a los demás.</p>
        </fieldset>

        {error && (
          <div className="notice notice-danger" role="alert">
            {error}
          </div>
        )}
        <div className="dialog-actions">
          <button type="button" className="btn" onClick={onClose}>
            Cancelar
          </button>
          <button type="submit" className="btn btn-primary" disabled={!ready || pending}>
            {pending ? "Guardando..." : artifact ? "Guardar cambios" : "Registrar artefacto"}
          </button>
        </div>
      </form>
    </div>
  );
}
