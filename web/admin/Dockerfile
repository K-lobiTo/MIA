# Panel de administración como sitio estático para Railway.
# Se compila una vez. Variables de compilación: VITE_API_URL (la URL de la API, obligatoria) y
# VITE_ENTRA_CLIENT_ID (el client ID que entrega TI; sin él el panel arranca pero no deja iniciar sesión).
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# Railway entrega las variables del servicio como argumentos de compilación.
ARG VITE_API_URL
ARG VITE_ENTRA_CLIENT_ID
ARG VITE_ENTRA_TENANT_ID
ARG VITE_ENTRA_AUTHORITY
RUN test -n "$VITE_API_URL" || (echo "Falta VITE_API_URL: la URL de la API, sin barra final" >&2 && exit 1)
RUN npm run build

FROM node:20-alpine
WORKDIR /app
RUN npm install -g serve@14
COPY --from=build /app/dist ./dist
# Railway define PORT; -s devuelve index.html para cualquier ruta (aplicación de una sola página).
ENV PORT=3000
CMD ["sh", "-c", "serve -s dist -l ${PORT}"]
