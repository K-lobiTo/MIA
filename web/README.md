# Aplicaciones web de MIA

Dos sitios independientes (React, TypeScript y Vite), cada uno con su propio `package.json`:

| Carpeta | Qué es | Quién lo usa | Puerto en desarrollo |
|---|---|---|---|
| [admin/](admin/README.md) | Panel de administración: inventario, artefactos y accesos, y uso | Quien mantiene MIA (clave de administración) | 3001 |
| [consulta/](consulta/README.md) | Consulta administrativa: preguntas en lenguaje natural sobre los dominios de una unidad | Personal administrativo (clave de su instancia, generada en el panel) | 3000 |

Ambos hablan solo con la API de MIA. Cada uno se instala y se prueba por separado (`npm install`, `npm test`, `npm run build` dentro de su carpeta).
