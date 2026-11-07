import { Anchor, Badge, Group, MultiSelect, Pill, Text } from "@mantine/core";
import { IconCheck, IconStack2 } from "@tabler/icons-react";
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
  const byId = useMemo(() => Object.fromEntries(domains.map((d) => [d.id, d])), [domains]);
  const grouped = groups.length > 1 || Boolean(groups[0]?.title);

  const data = useMemo(() => {
    // Con más de una unidad, dos dominios pueden llamarse igual ("Currículum"): la etiqueta (la que ven las
    // fichas y la búsqueda) lleva la unidad, y la opción de la lista muestra solo el nombre bajo su grupo.
    const item = (domain: Domain, unit: string | null) => ({
      value: domain.id,
      label: grouped && unit ? `${domain.name} (${unit})` : domain.name,
    });
    return grouped
      ? groups.map((group) => ({ group: group.title ?? "Otros", items: group.domains.map((d) => item(d, group.title)) }))
      : domains.map((d) => item(d, null));
  }, [groups, domains, grouped]);

  if (domains.length === 0) {
    return <Text c="dimmed">Esta Consulta todavía no tiene dominios para consultar.</Text>;
  }

  return (
    <section aria-label="Dominios" className="sidebar-section">
      <Text component="h2" className="sidebar-title">
        <IconStack2 size={14} stroke={2} aria-hidden />
        Dominios
      </Text>
      <Group gap="md">
        <Anchor component="button" type="button" fz="sm" fw={600} onClick={() => onChange(domains.map((d) => d.id))}>
          Todos
        </Anchor>
        <Anchor component="button" type="button" fz="sm" fw={600} onClick={() => onChange([])}>
          Ninguno
        </Anchor>
        <Text c="dimmed" fz="sm" ml="auto">
          {selected.length} de {domains.length}
        </Text>
      </Group>
      <MultiSelect
        aria-label="Dominios a consultar"
        placeholder={selected.length === 0 ? "Elige al menos un dominio" : undefined}
        data={data}
        value={selected}
        onChange={onChange}
        searchable
        clearable
        hidePickedOptions={false}
        nothingFoundMessage="Ningún dominio coincide"
        maxDropdownHeight={320}
        // Con muchos dominios elegidos las fichas se desplazan en vez de alargar el menú lateral.
        styles={{ pillsList: { maxHeight: 132, overflowY: "auto" } }}
        // La ficha recorta el texto largo; el nombre completo (con la unidad) queda en su descripción emergente.
        renderPill={({ option, onRemove, disabled }) => (
          <Pill withRemoveButton={!disabled} onRemove={onRemove} title={option.label}>
            {option.label}
          </Pill>
        )}
        renderOption={({ option, checked }) => {
          const domain = byId[option.value];
          return (
            <div style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
              <span style={{ width: 16, flex: "none", paddingTop: 2 }}>
                {checked && <IconCheck size={16} aria-hidden="true" />}
              </span>
              <div>
                <Group gap={6} wrap="nowrap">
                  <Text fw={600} fz="sm">
                    {domain?.name ?? option.label}
                  </Text>
                  {domain?.dynamic && (
                    <Badge
                      size="xs"
                      variant="light"
                      color="peach"
                      tt="none"
                      title="Su contenido cambia cada periodo y solo trae información vigente"
                    >
                      Dinámico
                    </Badge>
                  )}
                </Group>
                {domain?.description && (
                  <Text c="dimmed" fz="xs">
                    {domain.description}
                  </Text>
                )}
              </div>
            </div>
          );
        }}
      />
    </section>
  );
}
