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

Se compila con `npm run build` y se publica `dist/` como sitio estático (Render Static Sites o Vercel). Como el navegador llama directo a la API, hay que agregar la dirección del sitio a `CORS_ORIGINS` en la API y construir con la URL de la API (ver `docs/OPERACION.md`).
