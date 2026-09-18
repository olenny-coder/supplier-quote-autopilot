# ---------- Build Stage ----------
FROM node:22-alpine AS builder

WORKDIR /app

# The API base URL is baked in at build time (Vite inlines import.meta.env.*).
# VITE_API_URL is the documented name; VITE_API_BASE_URL is still forwarded so
# existing docker-compose files keep working as the client's fallback.
ARG VITE_API_URL
ARG VITE_API_BASE_URL

ENV VITE_API_URL=${VITE_API_URL}
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

COPY package*.json ./

RUN npm ci

COPY . .

RUN npm run build


# ---------- Production Stage ----------
FROM nginx:1.29-alpine

COPY --from=builder /app/dist /usr/share/nginx/html

COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]