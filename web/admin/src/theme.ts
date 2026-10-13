import { createTheme, type MantineColorsTuple } from "@mantine/core";

// Paletas de los cuatro colores de MIA (ver styles/tokens.css). `mia` va de #E0FBFC (paso 0) a un azul
// muy oscuro, pasando por #98C1D9 (paso 3) y #3D5A80 (paso 6); `coral` es #EE6C4D en el paso 5.
const mia: MantineColorsTuple = [
  "#e0fbfc", "#cdeef2", "#b6dde8", "#98c1d9", "#7aa6c4", "#5f89ac", "#3d5a80", "#324a6b", "#283b56", "#1e2d43",
];
const coral: MantineColorsTuple = [
  "#fdebe6", "#fbd9d0", "#f8bfb0", "#f5a28e", "#f18569", "#ee6c4d", "#d95635", "#b23a22", "#8c2d1a", "#6a2113",
];

// Mantine pinta con su gris los estados de pasar el mouse, los bordes y los fondos de campos y botones. Se
// reemplaza por tonos de la paleta: `gray` (modo claro) va del celeste #E0FBFC al azul pizarra #3D5A80, y `dark`
// (modo oscuro) va del blanco azulado al fondo azul marino, pasando por #98C1D9 y #3D5A80.
const gray: MantineColorsTuple = mia;
const dark: MantineColorsTuple = [
  "#e8f0f6", "#c3d6e3", "#98c1d9", "#7fa3bf", "#3d5a80", "#2c4565", "#1f3550", "#162434", "#11202f", "#0e1a27",
];

export const theme = createTheme({
  colors: { mia, coral, gray, dark },
  primaryColor: "mia",
  // Modo claro: #3D5A80. Modo oscuro: #98C1D9, que se lee sobre el fondo oscuro.
  primaryShade: { light: 6, dark: 3 },
  autoContrast: true,
  fontFamily: "var(--font)",
  fontFamilyMonospace: "var(--font-mono)",
  defaultRadius: "md",
  focusRing: "auto",
  headings: { fontWeight: "700" },
  components: {
    // Rótulos de campos y leyendas de grupos en negrita media, con aire entre el rótulo y el campo.
    InputWrapper: { styles: { label: { fontWeight: 600, marginBottom: 4 }, description: { marginBottom: 6 } } },
    Checkbox: { styles: { label: { fontWeight: 500 } } },
    Fieldset: { styles: { legend: { fontWeight: 700, fontSize: "0.95rem", marginBottom: 6 } } },
    Modal: { styles: { title: { fontWeight: 700, fontSize: "1.15rem" } } },
  },
});
