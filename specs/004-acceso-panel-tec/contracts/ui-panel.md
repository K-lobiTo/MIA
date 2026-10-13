# Contrato del panel: inicio de sesión

## Configuración de compilación

| Variable | Obligatoria | Uso |
|---|---|---|
| `VITE_API_URL` | sí (ya existía) | dirección de la API |
| `VITE_ENTRA_CLIENT_ID` | no para compilar; sí para iniciar sesión | client ID que entregue TI |
| `VITE_ENTRA_TENANT_ID` | no | por defecto, el del TEC |
| `VITE_ENTRA_AUTHORITY` | no, solo desarrollo | autoridad alternativa (servidor de identidad simulado) |

Sin `VITE_ENTRA_CLIENT_ID` el panel arranca y muestra "El inicio de sesión no está configurado".

## Estados de acceso

El panel está siempre en uno de estos estados (`auth/session.ts`):

| Estado | Qué se ve |
|---|---|
| `cargando` | pantalla en blanco breve mientras MSAL resuelve la redirección o la sesión guardada |
| `sin_sesion` | pantalla de inicio de sesión con el botón "Iniciar sesión con Microsoft" |
| `no_configurado` | pantalla de inicio de sesión con el aviso de configuración, sin botón |
| `iniciando` | la redirección a Microsoft está en curso |
| `activa` | el panel, con el correo y el alcance en la barra lateral |
| `rechazada(motivo)` | pantalla con el mensaje del motivo y la acción que corresponde |

Motivos de rechazo y su texto (`auth/errors.ts`, función pura que recibe estado HTTP y `code`):

| Origen | Mensaje | Acción |
|---|---|---|
| 403 `not_authorized` | "La cuenta {correo} no está autorizada para usar el panel de MIA. Pide acceso a quien administra MIA." | Cerrar sesión / probar con otra cuenta |
| 403 `mfa_required` | "El inicio de sesión no incluyó la verificación en dos pasos. Complétala en Microsoft e intenta de nuevo." | Volver a iniciar sesión |
| 401 `token_expired` o `invalid_token` tras un reintento con renovación | "Tu sesión venció. Inicia sesión de nuevo." | Iniciar sesión |
| 503 `login_not_configured` | "El inicio de sesión todavía no está disponible en esta instancia de MIA." | ninguna |
| 503 `identity_unavailable` | "No se pudo verificar tu identidad ahora mismo. Intenta de nuevo en unos minutos." | Reintentar |
| El navegador bloquea el almacenamiento o MSAL no puede iniciar | "Tu navegador bloquea el almacenamiento necesario para iniciar sesión. Revisa que no estés en una ventana privada estricta o que las cookies y el almacenamiento del sitio estén permitidos." | Reintentar |
| Cancelación o error de Microsoft | "No se completó el inicio de sesión en Microsoft." más el motivo si lo hay | Volver a intentar |
| Sin conexión | el mensaje de red que ya existe | Reintentar |

## Cliente de la API (`api/client.ts`)

- Antes de cada petición pide el token a `auth/session` (que guarda en memoria el token vigente y lo
  renueva en silencio cuando faltan menos de 5 minutos para que venza) y envía `Authorization: Bearer`. Nunca envía `X-Admin-Key`.
- Ante 401 `token_expired` o `invalid_token`, fuerza una renovación y reintenta **una vez**; si la
  renovación falla pasa a `rechazada("vencida")`. Las subidas de documentos de `useUploads` se
  reintentan con este mismo mecanismo (el reintento solo repite la petición ya fallida).
- Ante 403 `not_authorized` o `mfa_required` pasa a `rechazada(...)`. Un 403 `out_of_scope` o
  `global_only` es un error normal de la operación (mensaje en pantalla), no cierra la sesión.
- La descarga del CSV usa el mismo mecanismo.

## Qué guarda el navegador

Solo lo que MSAL guarda en `sessionStorage` (cuenta y tokens), que se borra al cerrar la pestaña y al
cerrar sesión. Nada en `localStorage`; la clave anterior `mia-admin-key` se borra al arrancar si existe.

## Pantallas y componentes

- **`LoginScreen`**: título "MIA, Panel de administración", botón, y el bloque de mensaje de los estados
  `no_configurado` y `rechazada`. Mismos tokens de color que el resto; legible en claro y oscuro; una
  columna centrada que cabe en 320 px.
- **Barra lateral** (`Layout`): al pie, el correo, el alcance ("Global" o los nombres de las unidades) y
  "Cerrar sesión". Se elimina `AdminKeyDialog`, el aviso de "solo lectura" y el atributo `needsAdmin` de
  los módulos.
- **Inventario**: sin las guardas por clave. "Nueva unidad" solo se ofrece con alcance global.
- **Artefactos y accesos**: oculta el bloque de topes globales cuando la API devuelve `global: null`;
  en el formulario, "Todos los dominios" y las unidades/dominios ajenos no se ofrecen sin alcance global
  (la lista de unidades y dominios que recibe ya viene recortada).
- **Uso**: la tarjeta de saldo solo se muestra con alcance global.

## Lógica pura con pruebas (Vitest)

- `auth/config.ts`: arma la configuración de MSAL desde variables, sin tocar `import.meta`.
- `auth/errors.ts`: (estado HTTP, `code`) a (acción, mensaje); incluye el texto de cada fila de arriba.
- `auth/capabilities.ts`: qué capacidades tiene una sesión
  (`canCreateUnit`, `canSeeBalance`, `canUseAllDomains`) a partir de `GET /me`.
