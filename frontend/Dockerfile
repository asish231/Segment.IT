# BhoomiAI frontend — built as static assets and served by nginx, which also
# reverse-proxies /segment, /jobs, /auth, /v1, /health to the api container.
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
# nginx's official entrypoint envsubst's *.template into conf.d/*.conf at container
# start, so the same image proxies to "api:8000" in docker-compose and to an ECS
# Cloud Map name (e.g. api.bhoomi.local:8000) in production via API_UPSTREAM.
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
ENV API_UPSTREAM=api:8000
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -qO- http://localhost/ || exit 1
