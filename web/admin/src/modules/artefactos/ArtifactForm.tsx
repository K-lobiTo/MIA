import { Button, Checkbox, Fieldset, Group, Modal, Paper, Stack, Text, TextInput, Textarea } from "@mantine/core";
import { useState } from "react";
import { ApiError } from "../../api/client";
import { useCreateArtifact, useUpdateArtifact } from "../../api/artifacts";
import type { Artifact, ArtifactCreated, ModeId, ModeInfo, UnitNode } from "../../api/types";
import { Notice } from "../../components/Notice";
import { MODE_LABEL, describeCost, pruneCoveredDomains } from "./accessUtils";
import { capabilities } from "../../auth/capabilities";
import { useMe } from "../../auth/session";
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
  const canUseAllDomains = capabilities(useMe()).canUseAllDomains;
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
    <Modal
      opened
      onClose={onClose}
      size="lg"
      centered
      closeOnClickOutside={false}
      title={artifact ? `Editar ${artifact.name}` : "Nuevo artefacto"}
    >
      <form onSubmit={submit}>
        <Stack gap="md">
          {!artifact && (
            <Text c="dimmed" fz="sm">
              Un artefacto es una aplicación que consulta a MIA. Al registrarlo se genera su clave, que se muestra una sola vez.
            </Text>
          )}
          {!artifact && <TextInput label="Nombre" data-autofocus value={name} onChange={(e) => setName(e.currentTarget.value)} />}
          <Textarea label="Descripción" rows={2} autosize minRows={2} value={description} onChange={(e) => setDescription(e.currentTarget.value)} />

          <Fieldset legend="Información que puede consultar" variant="unstyled">
            <Stack gap="xs">
              {(canUseAllDomains || allDomains) && (
                <Checkbox
                  checked={allDomains}
                  onChange={(e) => setAllDomains(e.currentTarget.checked)}
                  label="Todos los dominios"
                  description="Incluye los de programas que se creen después."
                />
              )}
              {!allDomains &&
                units.map((unit) => {
                  const unitChecked = unitIds.includes(unit.id);
                  return (
                    <Paper withBorder p="sm" radius="md" key={unit.id}>
                      <Checkbox
                        checked={unitChecked}
                        onChange={() => toggleUnit(unit.id)}
                        label={`${unit.name} (programa completo)`}
                        description="Incluye los dominios que se creen después en este programa."
                      />
                      <Stack gap={6} mt="xs" ml={28}>
                        {unit.domains.map((domain) => (
                          <Checkbox
                            key={domain.id}
                            disabled={unitChecked}
                            checked={unitChecked || domainIds.includes(domain.id)}
                            onChange={() => setDomainIds(toggle(domainIds, domain.id))}
                            label={domain.name}
                          />
                        ))}
                      </Stack>
                    </Paper>
                  );
                })}
              {!hasAccess && <Text c="dimmed" fz="sm">Elige al menos un dominio o programa.</Text>}
            </Stack>
          </Fieldset>

          <Fieldset legend="Modos de respuesta que puede usar" variant="unstyled">
            <Stack gap="xs">
              {ALL_MODES.map((mode) => {
                const info = modes.find((m) => m.id === mode);
                return (
                  <Checkbox
                    key={mode}
                    checked={selectedModes.includes(mode)}
                    onChange={() => setSelectedModes(toggle(selectedModes, mode))}
                    label={MODE_LABEL[mode]}
                    description={`${describeCost(info?.avg_cost_usd_7d)}${
                      info && !info.available ? " · todavía no está configurado en esta instancia" : ""
                    }`}
                  />
                );
              })}
              {selectedModes.length === 0 && <Text c="dimmed" fz="sm">Elige al menos un modo.</Text>}
            </Stack>
          </Fieldset>

          <Fieldset legend="Tope de gasto diario" variant="unstyled">
            <Stack gap="sm">
              <TextInput
                label="Tope total, para todos los modos (USD por día)"
                inputMode="decimal"
                value={dailyCap}
                onChange={(e) => setDailyCap(e.currentTarget.value)}
                error={capProblem ?? undefined}
                description={
                  dailyValue !== null
                    ? `${
                        selectedModes
                          .map((mode) => {
                            const approx = approxQueries(dailyValue, modes.find((m) => m.id === mode)?.avg_cost_usd_7d);
                            return approx === null ? null : `unas ${approx} consultas ${mode === "literal" ? "literales" : "con razonamiento"}`;
                          })
                          .filter(Boolean)
                          .join(" o ") || "sin consultas recientes para estimar cuántas alcanza"
                      } al día (según el costo medio de los últimos 7 días).`
                    : undefined
                }
              />
              <TextInput
                label="Tope menor solo para el modo con razonamiento (opcional)"
                inputMode="decimal"
                placeholder="Sin tope propio"
                value={reasoningCap}
                onChange={(e) => setReasoningCap(e.currentTarget.value)}
                description="Al alcanzarlo, el artefacto sigue respondiendo en los otros modos hasta el tope total."
              />
              <Text c="dimmed" fz="sm">
                Al alcanzar un tope el artefacto deja de responder hasta la medianoche (hora de Costa Rica), sin afectar a los demás.
              </Text>
            </Stack>
          </Fieldset>

          {error && <Notice tone="danger">{error}</Notice>}
          <Group justify="flex-end">
            <Button variant="default" onClick={onClose}>
              Cancelar
            </Button>
            <Button type="submit" disabled={!ready} loading={pending}>
              {artifact ? "Guardar cambios" : "Registrar artefacto"}
            </Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  );
}
