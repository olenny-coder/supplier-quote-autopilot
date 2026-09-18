# ---------- Build Stage ----------
FROM node:22-alpine AS builder

WORKDIR /app

# The API origin is baked into the bundle at build time. Pass the deployed API
# URL here; the default keeps local image builds working out of the box.
ARG VITE_API_URL=http://localhost:8000

ENV VITE_API_URL=${VITE_API_URL}

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
