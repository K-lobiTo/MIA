# Cliente web de MIA

Chat mínimo en TypeScript (Vite, sin framework) para consultar la API de MIA: se eligen uno o varios dominios en la barra lateral y se envían preguntas a `POST /query`. Cada respuesta muestra las fuentes y, desplegables, los fragmentos citados.

## Uso

Requiere Node 20 o superior.

```bash
cd web
npm install
npm run dev                                    # http://localhost:3000, contra la API de Render
MIA_API_URL=http://localhost:8000 npm run dev  # contra una API local
MIA_API_URL=https://<servicio>.up.railway.app npm run dev  # contra Railway
```

## Cómo funciona

- **Proxy de Vite:** la API no tiene CORS configurado, así que el navegador solo habla con `localhost:3000`, y el servidor de Vite reenvía `/api/*` a `MIA_API_URL` (por defecto la API de Render), con un timeout de 200 s por Render dormido y Gemini lento (`vite.config.ts`). Para publicar el cliente como sitio estático habría que habilitar CORS en la API (`CORSMiddleware` de FastAPI) y apuntar las llamadas directamente a su URL.
- **Selección de dominios:** se recuerda en el navegador (`localStorage`). La primera vez se marcan todos.
- **Errores:** un 502 (Gemini saturado) o un fallo de conexión muestran un mensaje con botón "Reintentar".
- **Formato de respuestas:** `src/format.ts` escapa el HTML y convierte el subconjunto de Markdown que usa Gemini (negritas y listas).

| Archivo | Contenido |
|---|---|
| `src/api.ts` | Llamadas a `/domains` y `/query`, tipos de la API |
| `src/main.ts` | Interfaz: dominios, mensajes, envío y reintentos |
| `src/format.ts` | Formato seguro de las respuestas |
| `src/style.css` | Estilos, con modo oscuro y diseño para móvil |
