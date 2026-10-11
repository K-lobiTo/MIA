# Panel de administración de MIA

Artefacto de gestión de MIA, con tres módulos: **Inventario** (unidades académicas, dominios, carpetas y documentos), **Artefactos y accesos** (claves, dominios y modos permitidos, topes de gasto) y **Uso** (métricas, gráficas y registro de consultas). Especificación en [specs/002-panel-administracion/](../../specs/002-panel-administracion/spec.md).

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

El panel pide iniciar sesión con la cuenta del TEC (Microsoft, `@itcr.ac.cr`, con verificación en dos pasos). Cada persona ve y opera solo lo de su unidad; el operador (alcance global) ve todo. Las personas autorizadas se gestionan con `python scripts/admin.py` (ver [docs/OPERACION.md](../../docs/OPERACION.md), "Acceso al panel con cuentas del TEC"). La sesión vive solo en la pestaña (`sessionStorage`); el token de identidad se renueva en silencio y, si no se puede, se pide iniciar sesión de nuevo. Los scripts de carga no pasan por aquí: usan `ADMIN_KEY` (clave de automatización).

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
| `src/components/` | Menú lateral con la sesión, pantalla de inicio de sesión |
| `src/styles/` | Variables de color (claro y oscuro) y estilos base |

Un módulo nuevo es una entrada más en `MODULES` (`src/modules/index.tsx`) más un grupo de rutas en la API.

## Publicación

Como servicio de Railway que sirve archivos estáticos, igual que la Consulta:

- **`Dockerfile`:** compila con Vite (falla si falta `VITE_API_URL`; `VITE_ENTRA_CLIENT_ID` es opcional al compilar) y sirve `dist` con `serve`. Escucha en `PORT` (en Railway, definir `PORT=3000` para que coincida con el puerto del dominio).
- **`railway.json`:** referencia de la configuración de build (Dockerfile y comprobación de salud en `/`). En Railway no hay que apuntar *Config-as-code* a este archivo: una ruta fija hace que se use el `Dockerfile` de la raíz (el de la API). El servicio usa el `Dockerfile` de `web/admin` por su *Root Directory*.
- **Probar la imagen en local:** `docker build --build-arg VITE_API_URL=<url de la API> -t mia-panel web/admin && docker run --rm -e PORT=3000 -p 3000:3000 mia-panel`.
- **Apagar y encender:** en Railway, *Deployments > Remove* y *Redeploy*.
- La API debe permitir el origen del panel (`CORS_ORIGINS`), y `VITE_API_URL` lleva `https://`.

Pasos completos y notas de seguridad en [docs/OPERACION.md](../../docs/OPERACION.md), sección "Publicar el panel como sitio estático".
