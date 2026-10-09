# Consulta administrativa como sitio estático para Railway (un servicio por instancia).
# Se compila una vez por servicio: la única variable de compilación es VITE_API_URL (la URL de la API).
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# Railway entrega las variables del servicio como argumentos de compilación.
ARG VITE_API_URL
RUN test -n "$VITE_API_URL" || (echo "Falta VITE_API_URL: la URL de la API, sin barra final" >&2 && exit 1)
RUN npm run build

FROM node:20-alpine
WORKDIR /app
RUN npm install -g serve@14
COPY --from=build /app/dist ./dist
# Railway define PORT; -s devuelve index.html para cualquier ruta (aplicación de una sola página).
ENV PORT=3000
CMD ["sh", "-c", "serve -s dist -l ${PORT}"]
