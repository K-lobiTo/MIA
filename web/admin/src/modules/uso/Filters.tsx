import { Group, Select } from "@mantine/core";
import { DatePickerInput, type DatePickerPreset } from "@mantine/dates";
import dayjs from "dayjs";
import { useArtifacts } from "../../api/artifacts";
import type { ModeId } from "../../api/types";
import { filtersReady, type PeriodName, type UsageFilters } from "../../api/usage";
import { Segmented } from "../../components/Segmented";

const PERIODS: Record<PeriodName, string> = { today: "Hoy", "7d": "7 días", "30d": "30 días", custom: "Rango" };
const ALL = "todos";
const MODES = [
  { value: ALL, label: "Todos" },
  { value: "literal", label: "Literal" },
  { value: "razonamiento", label: "Con razonamiento" },
];

const DAY = "YYYY-MM-DD";

/** Atajos del selector de rango. Ninguno pasa de 366 días, que es lo que acepta la API. */
function rangePresets(): DatePickerPreset<"range">[] {
  const today = dayjs();
  const monthStart = today.startOf("month");
  return [
    { label: "Este mes", value: [monthStart.format(DAY), today.format(DAY)] },
    {
      label: "Mes anterior",
      value: [monthStart.subtract(1, "month").format(DAY), monthStart.subtract(1, "day").format(DAY)],
    },
    { label: "Últimos 3 meses", value: [monthStart.subtract(2, "month").format(DAY), today.format(DAY)] },
    { label: "Últimos 12 meses", value: [monthStart.subtract(11, "month").format(DAY), today.format(DAY)] },
  ];
}

interface Props {
  filters: UsageFilters;
  onChange: (filters: UsageFilters) => void;
}

/** Filtros que controlan todo el módulo: período, artefacto y modo (USO-1). */
export function Filters({ filters, onChange }: Props) {
  const artifacts = useArtifacts(true);
  const set = (changes: Partial<UsageFilters>) => onChange({ ...filters, ...changes });
  const artifactOptions = [
    { value: ALL, label: "Todos" },
    ...(artifacts.data?.artifacts.map((artifact) => ({ value: artifact.id, label: artifact.name })) ?? []),
  ];

  return (
    <Group role="search" aria-label="Filtros del uso" gap="md" align="flex-end" wrap="wrap">
      <Segmented label="Período" value={filters.period} options={PERIODS} onChange={(period) => set({ period })} />
      {filters.period === "custom" && (
        <DatePickerInput
          type="range"
          label="Rango de fechas"
          placeholder="Elige el rango"
          valueFormat="D MMM YYYY"
          allowSingleDateInRange
          maxDate={dayjs().format(DAY)}
          presets={rangePresets()}
          value={[filters.from || null, filters.to || null]}
          onChange={([from, to]) => set({ from: from ?? "", to: to ?? "" })}
          description={!filtersReady(filters) ? "Elige la fecha inicial y la final." : undefined}
          w={280}
        />
      )}
      <Select
        label="Artefacto"
        data={artifactOptions}
        value={filters.artifactId || ALL}
        onChange={(value) => set({ artifactId: !value || value === ALL ? "" : value })}
        allowDeselect={false}
        w={260}
      />
      <Select
        label="Modo"
        data={MODES}
        value={filters.mode || ALL}
        onChange={(value) => set({ mode: !value || value === ALL ? "" : (value as ModeId) })}
        allowDeselect={false}
        w={180}
      />
    </Group>
  );
}
