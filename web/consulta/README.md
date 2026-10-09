# Consulta administrativa de MIA

Cliente web para que el personal administrativo (Coordinación y Asistencia Administrativa) pregunte en lenguaje natural sobre los documentos de su unidad. Se abre con la clave de un artefacto registrado en el panel de administración (`web/admin/`); el nombre de la instancia, los dominios, los modos de respuesta y los topes vienen de la API según esa clave, así que una misma compilación sirve para todas las instancias.

- **Dominios:** casillas por dominio (agrupados por unidad si hay más de una), con "Todos" y "Ninguno".
- **Modos:** Literal (lo que dice exactamente un documento) y Con razonamiento (combina, compara y calcula datos de varios documentos, mostrando los datos usados y el cálculo). Solo se muestran los que el artefacto tiene permitidos.
- **Respuestas:** con formato, con los documentos citados y los fragmentos desplegables, el modo y el tiempo. La respuesta "sin información suficiente" se distingue.
- **Calificación:** cada respuesta se puede marcar como útil o no útil, con un comentario opcional.
- **Topes y errores:** si un modo o el envío no están disponibles se explica el motivo; ante un error hay "Reintentar" y, en razonamiento, "Reintentar en modo literal".

## Uso

Requiere Node 20 o superior.

```bash
cd web/consulta
npm install
npm run dev                                                 # http://localhost:3000, contra la API local
MIA_API_URL=https://<servicio>.up.railway.app npm run dev   # contra otra API (p. ej. Railway)
npm test                                                    # pruebas de las funciones puras
npm run build                                               # genera dist/
```

En desarrollo el servidor de Vite hace de proxy de `/api` hacia la API (con 200 s de espera, porque el razonamiento tarda), así que no hace falta CORS.

## Qué se guarda en el navegador

Solo la clave, la selección de dominios y el modo, en `localStorage` de la dirección de cada instancia (dos direcciones distintas no comparten nada). **La conversación nunca se guarda**: las preguntas pueden contener datos personales y al recargar la página la conversación empieza vacía. El registro completo queda en la API, visible solo con la clave de administración.

## Publicar

Se compila una sola vez y se publica una vez por instancia, cada una en su dirección (p. ej. `mia-computacion` y `mia-administracion`). No hay configuración por instancia en la compilación: la única variable es `VITE_API_URL`.

```bash
VITE_API_URL=https://<servicio>.up.railway.app npm run build   # genera dist/
```

La API debe permitir el origen de cada sitio (`CORS_ORIGINS`). Pasos completos en [docs/OPERACION.md](../../docs/OPERACION.md), sección "Consulta administrativa".

## Estructura

| Carpeta | Contenido |
|---|---|
| `src/api/` | Cliente de la API (clave, tiempos de espera, errores), llamadas con TanStack Query y tipos |
| `src/state/` | Lógica sin interfaz y con pruebas: dominios recordados, modos disponibles, errores, conversación, fuentes |
| `src/format/` | Formateador de respuestas (negritas y listas) que nunca interpreta HTML |
| `src/components/` | Pantalla de clave, encabezado, dominios, modos, conversación, calificación y campo de pregunta |
| `src/styles/` | Variables de color con modo claro y oscuro, y estilos base |
