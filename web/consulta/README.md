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

Se compila una vez por instancia y se publica una vez por instancia, cada una en su dirección (p. ej. `mia-computacion` y `mia-administracion`), como servicios de Railway. No hay configuración por instancia en el código publicado: la única variable de compilación es `VITE_API_URL`.

- **`Dockerfile`:** compila con Vite (falla si falta `VITE_API_URL`) y sirve `dist` con `serve`, que devuelve `index.html` para cualquier ruta. Escucha en el `PORT` que da Railway.
- **`railway.json`:** build con el `Dockerfile`, comprobación de salud en `/` y redespliegue solo cuando cambia `web/consulta/`.
- **Probar la imagen en local:** `docker build --build-arg VITE_API_URL=<url de la API> -t mia-consulta . && docker run --rm -e PORT=8080 -p 8080:8080 mia-consulta`.
- **Apagar y encender:** en Railway, *Deployments > Remove* apaga el sitio (sin consumo) y *Redeploy* lo enciende.
- La API debe permitir el origen de cada sitio (`CORS_ORIGINS`).

Pasos completos en [docs/OPERACION.md](../../docs/OPERACION.md), sección "Consulta administrativa".

## Estructura

| Carpeta | Contenido |
|---|---|
| `src/api/` | Cliente de la API (clave, tiempos de espera, errores), llamadas con TanStack Query y tipos |
| `src/state/` | Lógica sin interfaz y con pruebas: dominios recordados, modos disponibles, errores, conversación, fuentes |
| `src/format/` | Formateador de respuestas (negritas y listas) que nunca interpreta HTML |
| `src/components/` | Pantalla de clave, encabezado, dominios, modos, conversación, calificación y campo de pregunta |
| `src/styles/` | Variables de color con modo claro y oscuro, y estilos base |
