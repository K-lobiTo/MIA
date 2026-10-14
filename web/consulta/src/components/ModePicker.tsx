import { Button, ComboboxPopover, Text } from "@mantine/core";
import { IconCheck, IconChevronUp } from "@tabler/icons-react";
import type { Availability } from "../state/modes";
import type { ModeId } from "../api/types";

interface Props {
  availability: Availability;
  onChange: (mode: ModeId) => void;
}

/** Selector del modo de respuesta, a la izquierda del campo de la pregunta (CON-2). Solo aparece si el
 * artefacto tiene más de un modo permitido; los no disponibles se ven deshabilitados con su motivo (CON-3). */
export function ModePicker({ availability, onChange }: Props) {
  const { modes, showSelector, effective } = availability;
  if (!showSelector) return null;

  const current = modes.find((m) => m.id === effective);
  const byId = Object.fromEntries(modes.map((m) => [m.id, m]));

  return (
    <ComboboxPopover
      data={modes.map((m) => ({ value: m.id, label: m.name, disabled: !m.available }))}
      value={effective}
      onChange={(value) => value && onChange(value as ModeId)}
      allowDeselect={false}
      comboboxProps={{ position: "top-start", width: 340, shadow: "md" }}
      renderOption={({ option, checked }) => {
        const mode = byId[option.value];
        return (
          <div style={{ display: "flex", gap: 10, alignItems: "flex-start", opacity: mode?.available === false ? 0.7 : 1 }}>
            <span style={{ width: 16, flex: "none", paddingTop: 2 }}>
              {checked && <IconCheck size={16} aria-hidden="true" />}
            </span>
            <div>
              <Text fw={600} fz="sm">
                {option.label}
              </Text>
              <Text c="dimmed" fz="xs">
                {mode?.description}
              </Text>
              {mode && !mode.available && mode.reason && (
                <Text fz="xs" style={{ color: "var(--warn)" }}>
                  {mode.reason}
                </Text>
              )}
            </div>
          </div>
        );
      }}
    >
      <ComboboxPopover.Target>
        <Button
          variant="default"
          size="md"
          rightSection={<IconChevronUp size={16} aria-hidden="true" />}
          aria-label={`Modo de respuesta: ${current?.name ?? "ninguno disponible"}`}
          title={current?.description}
          className="mode-button"
        >
          {current?.name ?? "Sin modo"}
        </Button>
      </ComboboxPopover.Target>
    </ComboboxPopover>
  );
}
