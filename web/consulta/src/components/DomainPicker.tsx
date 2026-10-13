import { Anchor, Checkbox, Group, Text } from "@mantine/core";
import { useMemo } from "react";
import type { Domain } from "../api/types";
import { groupByUnit } from "../state/domains";

interface Props {
  domains: Domain[];
  selected: string[];
  onChange: (ids: string[]) => void;
}

export function DomainPicker({ domains, selected, onChange }: Props) {
  const groups = useMemo(() => groupByUnit(domains), [domains]);
  const chosen = new Set(selected);

  if (domains.length === 0) {
    return <Text c="dimmed">Esta Consulta todavía no tiene dominios para consultar.</Text>;
  }

  const toggle = (id: string) => {
    onChange(chosen.has(id) ? selected.filter((s) => s !== id) : [...selected, id]);
  };

  return (
    <section aria-label="Dominios" className="sidebar-section">
      <h2>Dominios</h2>
      <Group gap="md">
        <Anchor component="button" type="button" fz="sm" fw={600} onClick={() => onChange(domains.map((d) => d.id))}>
          Todos
        </Anchor>
        <Anchor component="button" type="button" fz="sm" fw={600} onClick={() => onChange([])}>
          Ninguno
        </Anchor>
      </Group>
      {groups.map((group) => (
        <div key={group.title ?? "unico"}>
          {group.title && <div className="group-title">{group.title}</div>}
          {group.domains.map((domain) => (
            <div key={domain.id} className="pick">
              <Checkbox
                checked={chosen.has(domain.id)}
                onChange={() => toggle(domain.id)}
                label={domain.name}
                description={domain.description ? <span className="pick-description">{domain.description}</span> : undefined}
              />
            </div>
          ))}
        </div>
      ))}
    </section>
  );
}
