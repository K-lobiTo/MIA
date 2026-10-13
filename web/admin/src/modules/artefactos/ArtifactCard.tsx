import { Button, Group, Paper, Text } from "@mantine/core";
import type { Artifact, UnitNode } from "../../api/types";
import { StatusBadge } from "../../components/StatusBadge";
import { describeAccess, describeModes } from "./accessUtils";
import { Meter } from "./Meter";

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
    <Paper component="article" withBorder p="md" radius="md" className="art-card" aria-label={artifact.name}>
      <Group gap="sm" wrap="wrap">
        <span className="art-name">{artifact.name}</span>
        <StatusBadge tone={artifact.active ? "ok" : "neutral"}>{artifact.active ? "Activo" : "Desactivado"}</StatusBadge>
        <span className="art-key" title="Comienzo de su clave">
          {artifact.key_prefix}...
        </span>
        {(artifact.today.cap_reached || artifact.today.reasoning_cap_reached) && (
          <StatusBadge tone="danger">
            {artifact.today.cap_reached ? "Tope alcanzado" : "Tope de razonamiento alcanzado"}
          </StatusBadge>
        )}
        <Text span c="dimmed" fz="sm" ml="auto">
          {artifact.queries_last_7_days} {artifact.queries_last_7_days === 1 ? "consulta" : "consultas"} (7 días)
        </Text>
      </Group>
      {artifact.description && <Text c="dimmed">{artifact.description}</Text>}
      <dl className="art-meta">
        <dt>Dominios</dt>
        <dd>
          {describeAccess(artifact.access, units)}{" "}
          <span className="muted">({artifact.allowed_domain_count} en total)</span>
        </dd>
        <dt>Modos</dt>
        <dd>{describeModes(artifact.modes)}</dd>
        <dt>Gasto de hoy</dt>
        <dd>
          <Meter label="Tope diario total" spent={artifact.today.spent_usd} cap={artifact.daily_cap_usd} />
          {artifact.reasoning_daily_cap_usd !== null && (
            <Meter
              label="Tope de razonamiento"
              spent={artifact.today.reasoning_spent_usd}
              cap={artifact.reasoning_daily_cap_usd}
            />
          )}
        </dd>
      </dl>
      <Group gap="xs" mt={4}>
        <Button variant="default" size="compact-sm" onClick={onEdit} disabled={busy}>
          Editar
        </Button>
        <Button variant="default" size="compact-sm" onClick={onRegenerate} disabled={busy}>
          Regenerar clave
        </Button>
        <Button variant="default" size="compact-sm" onClick={onToggleActive} disabled={busy}>
          {artifact.active ? "Desactivar" : "Reactivar"}
        </Button>
      </Group>
    </Paper>
  );
}
