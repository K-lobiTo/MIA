import type { Availability } from "../state/modes";
import type { ModeId } from "../api/types";

interface Props {
  availability: Availability;
  onChange: (mode: ModeId) => void;
}

export function ModePicker({ availability, onChange }: Props) {
  const { modes, showSelector, effective, changed } = availability;
  if (!showSelector) return null;

  return (
    <section aria-label="Modo de respuesta">
      <h2>Modo de respuesta</h2>
      {changed && effective && (
        <p className="notice notice-warn" role="status">
          El modo que usabas ya no está disponible. Ahora se usa «{modes.find((m) => m.id === effective)?.name}».
        </p>
      )}
      {modes.map((mode) => (
        <label key={mode.id} className={`mode${mode.available ? "" : " disabled"}`}>
          <input
            type="radio"
            name="mode"
            value={mode.id}
            checked={effective === mode.id}
            disabled={!mode.available}
            onChange={() => onChange(mode.id)}
          />
          <span>
            <span className="name">{mode.name}</span>
            <span className="description">{mode.description}</span>
            {!mode.available && mode.reason && <span className="reason">{mode.reason}</span>}
          </span>
        </label>
      ))}
    </section>
  );
}
