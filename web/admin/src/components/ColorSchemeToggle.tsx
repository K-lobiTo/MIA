import { SegmentedControl, useMantineColorScheme, VisuallyHidden } from "@mantine/core";
import { IconDeviceDesktop, IconMoon, IconSun } from "@tabler/icons-react";

type Choice = "light" | "dark" | "auto";

const OPTIONS: { value: Choice; label: string; Icon: typeof IconSun }[] = [
  { value: "light", label: "Modo claro", Icon: IconSun },
  { value: "dark", label: "Modo oscuro", Icon: IconMoon },
  { value: "auto", label: "Seguir el modo del sistema", Icon: IconDeviceDesktop },
];

/** Interruptor de apariencia: claro, oscuro o el del sistema. Mantine recuerda la elección en el navegador. */
export function ColorSchemeToggle() {
  const { colorScheme, setColorScheme } = useMantineColorScheme();
  return (
    <SegmentedControl
      aria-label="Apariencia"
      fullWidth
      size="xs"
      value={colorScheme}
      onChange={(value) => setColorScheme(value as Choice)}
      data={OPTIONS.map(({ value, label, Icon }) => ({
        value,
        label: (
          <>
            <Icon size={16} aria-hidden="true" style={{ display: "block", margin: "0 auto" }} />
            <VisuallyHidden>{label}</VisuallyHidden>
          </>
        ),
      }))}
    />
  );
}
