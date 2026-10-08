import { formatUsd, meterLevel, percentUsed } from "./capMath";

/** Barra de gasto frente a un tope: el relleno cambia de verde a ámbar (desde 80 %) y a rojo (alcanzado). */
export function Meter({ label, spent, cap }: { label: string; spent: number; cap: number }) {
  const level = meterLevel(spent, cap);
  return (
    <div className="meter-row">
      <span className="meter-label">{label}</span>
      <div
        className={`meter meter-${level}`}
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(percentUsed(spent, cap))}
      >
        <div className="meter-fill" style={{ width: `${percentUsed(spent, cap)}%` }} />
      </div>
      <span className="meter-text">
        {formatUsd(spent)} / {formatUsd(cap)}
      </span>
    </div>
  );
}
