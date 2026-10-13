import { Radio, Stack } from "@mantine/core";
import type { Availability } from "../state/modes";
import type { ModeId } from "../api/types";
import { Notice } from "./Notice";

interface Props {
  availability: Availability;
  onChange: (mode: ModeId) => void;
}

export function ModePicker({ availability, onChange }: Props) {
  const { modes, showSelector, effective, changed } = availability;
  if (!showSelector) return null;

  return (
    <section aria-label="Modo de respuesta" className="sidebar-section">
      <h2>Modo de respuesta</h2>
      {changed && effective && (
        <Notice tone="warn">
          El modo que usabas ya no está disponible. Ahora se usa «{modes.find((m) => m.id === effective)?.name}».
        </Notice>
      )}
      <Radio.Group value={effective ?? ""} onChange={(value) => onChange(value as ModeId)} name="mode">
        <Stack gap={2}>
          {modes.map((mode) => (
            <div key={mode.id} className="pick" style={mode.available ? undefined : { opacity: 0.65 }}>
              <Radio
                value={mode.id}
                disabled={!mode.available}
                label={mode.name}
                description={
                  <>
                    <span className="pick-description">{mode.description}</span>
                    {!mode.available && mode.reason && <span className="pick-reason">{mode.reason}</span>}
                  </>
                }
              />
            </div>
          ))}
        </Stack>
      </Radio.Group>
    </section>
  );
}
