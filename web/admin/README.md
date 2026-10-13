# Panel de administración de MIA

Artefacto de gestión de MIA, con tres módulos: **Inventario** (programas, dominios, carpetas y documentos), **Artefactos y accesos** (claves, dominios y modos permitidos, topes de gasto) y **Uso** (métricas, gráficas y registro de consultas). Especificación en [specs/002-panel-administracion/](../../specs/002-panel-administracion/spec.md).

## Uso

Requiere Node 20 o superior.

```bash
cd web/admin
npm install
npm run dev                                       # http://localhost:3001, contra la API local
MIA_API_URL=https://<servicio>.up.railway.app npm run dev   # contra Railway
npm run typecheck && npm test && npm run build
```

## Inicio de sesión

El panel pide iniciar sesión con la cuenta del TEC (Microsoft, `@itcr.ac.cr`, con verificación en dos pasos). Cada persona ve y opera solo lo de su programa; el operador (alcance global) ve todo. Las personas autorizadas se gestionan con `python scripts/admin.py` (ver [docs/OPERACION.md](../../docs/OPERACION.md), "Acceso al panel con cuentas del TEC"). Mientras no haya client ID de TI (prototipo), la pantalla de entrada también deja entrar con la clave de administración (`ADMIN_KEY`, alcance global), que se guarda solo en la pestaña. La sesión vive solo en la pestaña (`sessionStorage`); el token de identidad se renueva en silencio y, si no se puede, se pide iniciar sesión de nuevo. Los scripts de carga no pasan por aquí: usan `ADMIN_KEY` por la API.

Variables de **compilación** (`.env.local` o en la orden):

| Variable | Para qué |
|---|---|
| `VITE_API_URL` | dirección de la API al publicar (en desarrollo se usa el proxy `/api`) |
| `VITE_ENTRA_CLIENT_ID` | client ID de la aplicación que registra TI; sin él el panel arranca y avisa que el inicio de sesión no está configurado |
| `VITE_ENTRA_TENANT_ID` | opcional, por defecto el directorio del TEC |
| `VITE_ENTRA_AUTHORITY` | opcional, solo desarrollo: autoridad alternativa (el Microsoft simulado) |

**Probar sin el client ID real** (desarrollo): `python scripts/idp_simulado.py` levanta un Microsoft simulado (`https://localhost:9000`, certificado autofirmado) y la API con datos de ejemplo en el puerto 8000; luego, en esta carpeta, `VITE_ENTRA_CLIENT_ID=cliente-de-prueba VITE_ENTRA_AUTHORITY=https://localhost:9000/1119bb90-88ba-4894-b7f1-de26e129d977 npm run dev` y aceptar el certificado en el navegador. Ofrece cuentas de cada alcance, una no listada y una sin segundo factor (detalle en [specs/004-acceso-panel-tec/quickstart.md](../../specs/004-acceso-panel-tec/quickstart.md)).

## Estructura

| Carpeta | Contenido |
|---|---|
| `src/api/` | Cliente tipado de la API (token de identidad con renovación y un reintento) y hooks de TanStack Query |
| `src/auth/` | Inicio de sesión: configuración de MSAL, estado de la sesión, mensajes de rechazo y capacidades por alcance |
| `src/modules/inventario/` | Árbol, búsqueda, formularios, subida de documentos |
| `src/modules/artefactos/` | Lista y formulario de artefactos, clave de una sola vez, topes |
| `src/modules/uso/` | Filtros, indicadores, gráfica, tablas, registro de consultas, saldo |
| `src/components/` | Marco con el menú lateral y la sesión (`AppShell` de Mantine), pantalla de inicio de sesión |
| `src/theme.ts` | Tema de Mantine: paletas y tipografía, derivadas de los colores de `styles/tokens.css` |
| `src/styles/` | Variables de color (claro y oscuro) y estilos base |

Un módulo nuevo es una entrada más en `MODULES` (`src/modules/index.tsx`) más un grupo de rutas en la API.

## Interfaz: Mantine

El panel usa [Mantine](https://mantine.dev/) (licencia MIT) como librería de componentes, en lugar de CSS escrito a mano para cada elemento. Se eligió por traer en un solo paquete lo que el panel necesita (selector de fechas con rango y atajos, marco con barra lateral, selects, modales, tablas y modo oscuro) sin sumar Tailwind. Las alternativas revisadas y por qué no: shadcn/ui exige Tailwind y deja código copiado que mantener; Ant Design es pesado y no se confirmó su español ni su modo oscuro; el selector de rango de MUI está en su nivel de pago.

Paquetes: `@mantine/core`, `@mantine/hooks`, `@mantine/dates` (con `dayjs`) y `@tabler/icons-react` para los iconos. Se importan por nombre, así el build solo incluye lo que se usa.

**Reglas de uso**

- **Paleta de cuatro colores** (la #03 de [docs/PALETAS.md](../../docs/PALETAS.md), donde están guardadas las otras cinco candidatas para probar después): `#3D5A80` (azul pizarra: acento, botones, módulo activo), `#98C1D9` (azul cielo: acento en modo oscuro y tercera serie de las gráficas), `#E0FBFC` (celeste claro: fondos suaves y estado seleccionado) y `#EE6C4D` (coral: resalte, como la barra de gasto desde 80 % de un tope y la segunda serie de las gráficas). Viven en `src/styles/tokens.css` (variables CSS, con su versión oscura) y en `src/theme.ts` (paletas `mia` y `coral` de Mantine, con `primaryShade` 6 en claro y 3 en oscuro). Si cambia un color de marca, se cambia en los dos archivos. No se definen colores sueltos en los componentes. El coral puro tiene poco contraste con texto sobre blanco (3.05:1): se usa en rellenos y gráficas, y para avisos de error y advertencia se usan sus pasos oscuros (`--danger`, `--warn`).
- **Sin grises de Mantine:** en `theme.ts`, `gray` (modo claro) y `dark` (modo oscuro) están reemplazados por tonos de la paleta, así que los estados de pasar el mouse, los bordes y los fondos de campos y botones salen en celeste (`#E0FBFC`) y azul. El módulo activo del menú usa `--selected`, un paso más marcado que el de pasar el mouse. No usar `color="gray"` ni colores `gray-*` en componentes nuevos. "Otros" en las gráficas es un azul pizarra apagado (`--series-other`), no un gris.
- **Capas de CSS:** `main.tsx` importa los estilos de Mantine en su versión de capa (`styles.layer.css`), así los estilos propios (sin capa) siempre prevalecen, sin importar el orden de carga. Consecuencia: **no** escribir reglas globales sobre elementos (`button`, `a`, `input`, `table`...), porque pisarían a los componentes de Mantine; usar clases propias.
- **Variables de Mantine:** `tokens.css` asigna `--mantine-color-body`, `-text`, `-dimmed` y `-default-border` a la paleta propia; así `c="dimmed"` y los bordes salen del mismo color que el resto.
- **Modo claro y oscuro:** `MantineProvider` con `defaultColorScheme="auto"` sigue el modo del sistema, y el interruptor del menú lateral (`components/ColorSchemeToggle.tsx`: claro, oscuro, sistema) permite fijarlo; Mantine recuerda la elección en `localStorage` (`mantine-color-scheme-value`). Las variables oscuras de `tokens.css` se activan con el atributo `data-mantine-color-scheme="dark"` de `<html>`, no con `@media`; un script en `index.html` lo pone antes de pintar para evitar el parpadeo.
- **Estilos:** `main.tsx` importa primero los estilos de Mantine (`@mantine/core/styles.css`, `@mantine/dates/styles.css`) y después los propios, que prevalecen. Preferir las propiedades de los componentes (`color`, `size`, `variant`, espaciados `p`, `mt`, `gap`) a CSS nuevo.
- **Fechas en español:** `main.tsx` registra el locale `es` de `dayjs` y envuelve la aplicación en `DatesProvider` (semana desde el lunes). Los selectores guardan y envían las fechas como `AAAA-MM-DD`, tal como las espera la API.
- **Componentes compartidos:** `src/components/Segmented.tsx` (selector de una opción entre pocas, sobre `SegmentedControl`). Antes de escribir un componente nuevo, revisar si Mantine ya lo trae.
- **Avisos y estados:** `components/Notice.tsx` (tonos `info`, `ok`, `warn`, `danger`) y `components/StatusBadge.tsx` (tonos `ok`, `warn`, `danger`, `info`, `neutral`) usan los colores de la paleta; no usar `Alert` ni `Badge` directamente con colores de Mantine. Un estado siempre lleva texto, nunca solo color. Diálogos con `Modal` (los de formularios no se cierran al hacer clic fuera, para no perder lo escrito; el de la clave nueva solo con "Ya la guardé"), tablas con `Table` y `Table.ScrollContainer`, diálogo de campos de texto genérico en `components/FormDialog.tsx`.
- **Tipografía:** rótulos y leyendas en negrita media y títulos en negrita, definidos en `theme.ts` (`components` y `headings`). Los números grandes (indicadores del Uso, saldo) llevan aire arriba y abajo para no quedar pegados a los textos de al lado.
- **Router:** los enlaces del menú son `NavLink` de Mantine con `component={RouterLink}` (de `react-router-dom`), para conservar `HashRouter`.
- **Accesibilidad:** se conservan las etiquetas `aria-label`, las tablas alternativas de las gráficas y el aro de foco. Cualquier componente nuevo debe poder usarse con teclado.
- **Las gráficas siguen siendo SVG propio** (`modules/uso/UsageChart.tsx`), con la paleta categórica `--series-1..8` validada para ambos modos. No se reemplazan por `@mantine/charts` para no perder esa validación ni la tabla alternativa.
- **Alcance de Mantine en MIA:** solo los artefactos con cliente propio, que son este panel y la Consulta administrativa (`web/consulta/`, ya migrada, con otra paleta; ver su [README](../consulta/README.md#interfaz-mantine)). El chatbot que se incorpore en sistemas existentes **no** debe usar Mantine: sus estilos globales y variables CSS chocarían con los del sistema anfitrión; irá como un componente aislado (Shadow DOM o CSS con prefijo propio). El bot de WhatsApp no tiene interfaz propia.

**Estado de la migración**

| Parte | Estado |
|---|---|
| Proveedor, tema y marco con menú lateral | Hecho |
| Módulo Uso (selector de rango con atajos, filtros, indicadores, tablas, registro, detalle en modal, Por día / Por mes) | Hecho (la gráfica de barras sigue siendo SVG propio) |
| Artefactos (tarjetas, formulario, clave de una sola vez, confirmación) | Hecho |
| Inventario (árbol con botones y avisos de Mantine, diálogos, subida) | Hecho (el árbol es una estructura propia) |
| Pantalla de inicio de sesión y diálogos genéricos (`FormDialog`) | Hecho |
| Consulta administrativa (`web/consulta/`) | Hecho (paleta Vanilla Style; ver su README) |

Las clases propias de botones, campos, tarjetas, avisos y diálogos (`.btn`, `.card`, `.field`, `.badge`, `.notice`, `.dialog`) se eliminaron: todo el panel usa Mantine.

## Publicación

Como servicio de Railway que sirve archivos estáticos, igual que la Consulta:

- **`Dockerfile`:** compila con Vite (falla si falta `VITE_API_URL`; `VITE_ENTRA_CLIENT_ID` es opcional al compilar) y sirve `dist` con `serve`. Escucha en `PORT` (en Railway, definir `PORT=3000` para que coincida con el puerto del dominio).
- **`railway.json`:** referencia de la configuración de build (Dockerfile y comprobación de salud en `/`). En Railway no hay que apuntar *Config-as-code* a este archivo: una ruta fija hace que se use el `Dockerfile` de la raíz (el de la API). El servicio usa el `Dockerfile` de `web/admin` por su *Root Directory*.
- **Probar la imagen en local:** `docker build --build-arg VITE_API_URL=<url de la API> -t mia-panel web/admin && docker run --rm -e PORT=3000 -p 3000:3000 mia-panel`.
- **Apagar y encender:** en Railway, *Deployments > Remove* y *Redeploy*.
- La API debe permitir el origen del panel (`CORS_ORIGINS`), y `VITE_API_URL` lleva `https://`.

Pasos completos y notas de seguridad en [docs/OPERACION.md](../../docs/OPERACION.md), sección "Publicar el panel como sitio estático".
