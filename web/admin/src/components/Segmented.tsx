import { SegmentedControl } from "@mantine/core";

interface Props<T extends string> {
  label: string;
  value: T;
  options: Record<T, string>;
  onChange: (value: T) => void;
}

/** Selector de una opción entre pocas (período, métrica, desglose...), con el color del módulo de administración. */
export function Segmented<T extends string>({ label, value, options, onChange }: Props<T>) {
  const data = (Object.keys(options) as T[]).map((key) => ({ value: key, label: options[key] }));
  return (
    <SegmentedControl
      aria-label={label}
      size="sm"
      data={data}
      value={value}
      onChange={(next) => onChange(next as T)}
    />
  );
}
