import { createTheme, type MantineColorsTuple } from "@mantine/core";

// Paletas de la paleta Vanilla Style (ver styles/tokens.css): `vanilla` es el violeta #6D597A (paso 6) con
// sus tintes y sombras; `coral` es #E56B6F (paso 5); `peach` es #EAAC8B (paso 4).
const vanilla: MantineColorsTuple = [
  "#f5eff7", "#e9dfee", "#d8c8e0", "#c2aacf", "#a68bb7", "#8a709a", "#6d597a", "#5b4a67", "#4a3c54", "#392e41",
];
const coral: MantineColorsTuple = [
  "#fdeced", "#fad9da", "#f6bcbe", "#f19b9e", "#ec8084", "#e56b6f", "#cf5559", "#a63a45", "#842c36", "#631f28",
];
const peach: MantineColorsTuple = [
  "#fdf4ee", "#fbe7db", "#f6d8c5", "#f1c8ad", "#eaac8b", "#dd9570", "#c47c58", "#a3633f", "#7f4c30", "#5c3822",
];

// Mantine pinta con su gris los estados de pasar el mouse, los bordes y los fondos de campos y botones. Se
// reemplaza por tonos del durazno y del violeta (modo claro) y por violetas oscuros (modo oscuro).
const gray: MantineColorsTuple = [
  "#fdf4ee", "#fbe7db", "#f6d8c5", "#f1c8ad", "#e9b79c", "#a38a95", "#6d597a", "#5b4a67", "#4a3c54", "#392e41",
];
const dark: MantineColorsTuple = [
  "#f2eaf3", "#d9cde0", "#bdafc4", "#9d8ca6", "#4d3c57", "#3a2b42", "#2e2236", "#251c2b", "#1e1623", "#1a141f",
];

export const theme = createTheme({
  colors: { vanilla, coral, peach, gray, dark },
  primaryColor: "vanilla",
  // Modo claro: #6D597A. Modo oscuro: un violeta claro (#C2AACF) que se lee sobre el fondo oscuro.
  primaryShade: { light: 6, dark: 3 },
  autoContrast: true,
  fontFamily: "var(--font)",
  defaultRadius: "md",
  focusRing: "auto",
  headings: { fontWeight: "700" },
  components: {
    InputWrapper: { styles: { label: { fontWeight: 600, marginBottom: 4 }, description: { marginBottom: 6 } } },
    Checkbox: { styles: { label: { fontWeight: 500 } } },
    Radio: { styles: { label: { fontWeight: 500 } } },
  },
});
