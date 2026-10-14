# Consulta administrativa de MIA

Cliente web para que el personal administrativo (Coordinación y Asistencia Administrativa) pregunte en lenguaje natural sobre los documentos de su unidad. Se abre con la clave de un artefacto registrado en el panel de administración (`web/admin/`); el nombre de la instancia, los dominios, los modos de respuesta y los topes vienen de la API según esa clave, así que una misma compilación sirve para todas las instancias.

- **Dominios:** un `MultiSelect` de Mantine en el menú lateral (agrupado por unidad si hay más de una, con búsqueda, fichas, "Todos", "Ninguno" y el recuento de elegidos).
- **Modos:** Literal (lo que dice exactamente un documento) y Con razonamiento (combina, compara y calcula datos de varios documentos, mostrando los datos usados y el cálculo). Se elige con un `ComboboxPopover` de Mantine **a la izquierda del campo de la pregunta** (en pantallas angostas pasa a la línea de arriba); cada opción explica el modo y los no disponibles se ven deshabilitados con su motivo. Solo se muestran los que el artefacto tiene permitidos.
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

## Clave fija (opcional)

Si el servicio publicado tiene la variable de entorno `ARTIFACT_KEY`, `docker-entrypoint.sh` la escribe en `dist/config.js` al arrancar y la Consulta usa esa clave sin pedirla (no muestra "Cambiar clave"; si la API la rechaza, avisa que la clave configurada no es válida). En desarrollo (`npm run dev`) no hay clave fija. **`/config.js` es público: cualquiera que abra el sitio puede leer la clave.** Solo para demostraciones con un artefacto sin información sensible; ver [docs/OPERACION.md](../../docs/OPERACION.md).

## Qué se guarda en el navegador

Solo la clave, la selección de dominios y el modo, en `localStorage` de la dirección de cada instancia (dos direcciones distintas no comparten nada). **La conversación nunca se guarda**: las preguntas pueden contener datos personales y al recargar la página la conversación empieza vacía. El registro completo queda en la API, visible solo con la clave de administración.

## Publicar

Se compila una vez por instancia y se publica una vez por instancia, cada una en su dirección (p. ej. `mia-computacion` y `mia-administracion`), como servicios de Railway. No hay configuración por instancia en el código publicado: la única variable de compilación es `VITE_API_URL`.

- **`Dockerfile`:** compila con Vite (falla si falta `VITE_API_URL`) y sirve `dist` con `serve`, que devuelve `index.html` para cualquier ruta. Escucha en el `PORT` que da Railway.
- **`railway.json`:** referencia de la configuración de build (Dockerfile y comprobación de salud en `/`). En Railway no hay que apuntar *Config-as-code* a este archivo: una ruta fija hace que se use el `Dockerfile` de la raíz (el de la API). El servicio usa el `Dockerfile` de `web/consulta` por su *Root Directory*.
- **Probar la imagen en local:** `docker build --build-arg VITE_API_URL=<url de la API> -t mia-consulta . && docker run --rm -e PORT=8080 -p 8080:8080 mia-consulta`.
- **Apagar y encender:** en Railway, *Deployments > Remove* apaga el sitio (sin consumo) y *Redeploy* lo enciende.
- La API debe permitir el origen de cada sitio (`CORS_ORIGINS`).

Pasos completos en [docs/OPERACION.md](../../docs/OPERACION.md), sección "Consulta administrativa".

## Interfaz: Mantine

La Consulta usa [Mantine](https://mantine.dev/) como librería de componentes, igual que el panel de administración, con la paleta **Vanilla Style (#05 de [docs/PALETAS.md](../../docs/PALETAS.md))**: violeta `#6D597A` (acento, botones, burbuja de la pregunta), rosa palo `#B56576`, coral `#E56B6F` y durazno `#EAAC8B` (en tintes claros, para fondos suaves y estado al pasar el mouse). Las reglas generales de uso (capas de CSS, sin grises de Mantine, avisos y tipografía) están en [web/admin/README.md](../admin/README.md#interfaz-mantine); aquí solo lo propio de esta aplicación:

- **Tema:** `src/theme.ts` (escalas `vanilla`, `coral` y `peach`, y `gray` y `dark` reemplazados por tonos de la paleta) y `src/styles/tokens.css` (variables CSS con su versión oscura). Se cambian juntos. La paleta no trae un color claro ni uno oscuro para texto, así que los fondos suaves son tintes del durazno y del violeta y el texto usa violetas oscuros; el coral y el durazno puros tienen poco contraste sobre blanco y solo se usan en rellenos, nunca como texto.
- **Marco:** `AppShell` con encabezado (nombre de la instancia, interruptor de apariencia, "Cambiar clave") y menú lateral (dominios). El selector de modo va junto al campo de la pregunta (`components/ModePicker.tsx`, dentro de `Composer`). En pantallas angostas el menú se despliega con el botón del encabezado y el interruptor pasa a él.
- **Modo claro, oscuro o del sistema:** `components/ColorSchemeToggle.tsx`; la elección se recuerda en el navegador (`mantine-color-scheme-value`) y un script en `index.html` la aplica antes de pintar.
- **Piezas:** `Notice` (avisos con los colores de la paleta, copia del panel: no hay paquete compartido), `ComboboxPopover` (modo), `MultiSelect` (dominios), `Textarea` con crecimiento automático, `Button`, `PasswordInput`.
- **Lo que se conserva a mano:** las burbujas de la conversación (`.message` en `styles/base.css`) y el formateador de respuestas, que nunca interpreta HTML.

## Estructura

| Carpeta | Contenido |
|---|---|
| `src/api/` | Cliente de la API (clave, tiempos de espera, errores), llamadas con TanStack Query y tipos |
| `src/state/` | Lógica sin interfaz y con pruebas: dominios recordados, modos disponibles, errores, conversación, fuentes |
| `src/format/` | Formateador de respuestas (negritas y listas) que nunca interpreta HTML |
| `src/components/` | Pantalla de clave, encabezado, dominios, modos, conversación, calificación y campo de pregunta |
| `src/theme.ts` | Tema de Mantine con la paleta Vanilla Style |
| `src/styles/` | Variables de color con modo claro y oscuro, y estilos base |
