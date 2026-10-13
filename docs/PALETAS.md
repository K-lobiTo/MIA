# Paletas de color de MIA

Paletas candidatas para los artefactos con interfaz propia. Se guardan aquí para probarlas más adelante, una por una, sin volver a buscarlas. Cada paleta son cuatro colores, en el orden en que se presentaron.

Hoy el Panel de administración usa la **#03**. Cómo cambiar de paleta en el panel: ver "Probar otra paleta" más abajo.

## #00 Eagle Style

| Color | Contraste con blanco | Contraste con fondo oscuro (#162434) |
|---|---|---|
| `#7CF6FD` | 1.28:1 | 12.32:1 |
| `#317AC7` | 4.43:1 | 3.55:1 |
| `#FCF9BF` | 1.08:1 | 14.55:1 |
| `#707D9D` | 4.11:1 | 3.82:1 |

## #01 Major Style

| Color | Contraste con blanco | Contraste con fondo oscuro (#162434) |
|---|---|---|
| `#76C893` | 2.01:1 | 7.82:1 |
| `#52B69A` | 2.47:1 | 6.37:1 |
| `#34A0A4` | 3.13:1 | 5.02:1 |
| `#168AAD` | 3.98:1 | 3.95:1 |

## #02 Glamour Style

| Color | Contraste con blanco | Contraste con fondo oscuro (#162434) |
|---|---|---|
| `#CB997E` | 2.50:1 | 6.28:1 |
| `#DDBEA9` | 1.75:1 | 8.99:1 |
| `#FFE8D6` | 1.18:1 | 13.30:1 |
| `#B7B7A4` | 2.03:1 | 7.73:1 |

## #03 Killer Style **(la que usa hoy el Panel de administración)**

| Color | Contraste con blanco | Contraste con fondo oscuro (#162434) |
|---|---|---|
| `#3D5A80` | 7.06:1 | 2.22:1 |
| `#98C1D9` | 1.92:1 | 8.21:1 |
| `#E0FBFC` | 1.08:1 | 14.50:1 |
| `#EE6C4D` | 3.05:1 | 5.16:1 |

## #04 Energy Style

| Color | Contraste con blanco | Contraste con fondo oscuro (#162434) |
|---|---|---|
| `#CAD2C5` | 1.55:1 | 10.13:1 |
| `#84A98C` | 2.61:1 | 6.01:1 |
| `#52796F` | 4.86:1 | 3.24:1 |
| `#354F52` | 8.78:1 | 1.79:1 |

## #05 Vanilla Style

| Color | Contraste con blanco | Contraste con fondo oscuro (#162434) |
|---|---|---|
| `#6D597A` | 6.25:1 | 2.52:1 |
| `#B56576` | 4.13:1 | 3.81:1 |
| `#E56B6F` | 3.15:1 | 4.99:1 |
| `#EAAC8B` | 1.95:1 | 8.06:1 |

Lectura de los contrastes: para texto normal se necesita al menos 4.5:1; para elementos gráficos (barras, íconos, bordes de campos), al menos 3:1. Un color con menos de 3:1 contra el fondo solo sirve como relleno decorativo o fondo suave, nunca como texto ni como única señal. Los contrastes se calcularon con la fórmula de luminancia relativa de WCAG 2.

## Probar otra paleta

En el Panel de administración los colores salen de dos archivos, que hay que cambiar juntos (ver "Interfaz: Mantine" en [web/admin/README.md](../web/admin/README.md)):

1. `web/admin/src/styles/tokens.css`: variables `--accent`, `--secondary`, `--accent-soft`, `--highlight`, `--selected` y las series de las gráficas `--series-1..8`, cada una con su versión del modo oscuro.
2. `web/admin/src/theme.ts`: las escalas `mia` y `coral` de Mantine (y `gray` y `dark`, que reemplazan los grises de Mantine por tonos de la paleta).

Pasos sugeridos: asignar los cuatro colores a un rol cada uno (acento principal oscuro, acento secundario, fondo suave, resalte), generar la escala de diez pasos de Mantine a partir de ellos, y revisar con capturas en modo claro y oscuro que ningún texto quede bajo 4.5:1 y que las series de las gráficas se distingan entre sí. Una paleta con varios colores claros (como #00 o #02) probablemente necesite un cuarto color oscuro para el texto y el acento.
