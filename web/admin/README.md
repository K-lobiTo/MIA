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

La clave de administración (`ADMIN_KEY` de la API) se pide la primera vez y se recuerda en el navegador. Sin clave se puede ver el inventario, pero no crear, subir ni usar los otros dos módulos.

## Estructura

| Carpeta | Contenido |
|---|---|
| `src/api/` | Cliente tipado de la API, manejo de la clave y hooks de TanStack Query |
| `src/modules/inventario/` | Árbol, búsqueda, formularios, subida de documentos |
| `src/modules/artefactos/` | Lista y formulario de artefactos, clave de una sola vez, topes |
| `src/modules/uso/` | Filtros, indicadores, gráfica, tablas, registro de consultas, saldo |
| `src/components/` | Menú lateral, diálogo de clave |
| `src/styles/` | Variables de color (claro y oscuro) y estilos base |

Un módulo nuevo es una entrada más en `MODULES` (`src/App.tsx`) más un grupo de rutas en la API.

## Publicación

Como servicio de Railway que sirve archivos estáticos, igual que la Consulta:

- **`Dockerfile`:** compila con Vite (falla si falta `VITE_API_URL`) y sirve `dist` con `serve`. Escucha en `PORT` (en Railway, definir `PORT=3000` para que coincida con el puerto del dominio).
- **`railway.json`:** referencia de la configuración de build (Dockerfile y comprobación de salud en `/`). En Railway no hay que apuntar *Config-as-code* a este archivo: una ruta fija hace que se use el `Dockerfile` de la raíz (el de la API). El servicio usa el `Dockerfile` de `web/admin` por su *Root Directory*.
- **Probar la imagen en local:** `docker build --build-arg VITE_API_URL=<url de la API> -t mia-panel web/admin && docker run --rm -e PORT=3000 -p 3000:3000 mia-panel`.
- **Apagar y encender:** en Railway, *Deployments > Remove* y *Redeploy*.
- La API debe permitir el origen del panel (`CORS_ORIGINS`), y `VITE_API_URL` lleva `https://`.

Pasos completos y notas de seguridad en [docs/OPERACION.md](../../docs/OPERACION.md), sección "Publicar el panel como sitio estático".
