# ---------------------------------------------------------------------------
# Stage 1 – build the Vite/React app
# ---------------------------------------------------------------------------
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies first (layer-cache friendly)
COPY package.json package-lock.json* ./
RUN npm install --frozen-lockfile || npm install

# Frontend calls the backend on its own domain, so the full URL is baked in
# at build time via this build arg.
ARG VITE_BACKEND_URL=https://api-tutorai.aditya-raj.site
ENV VITE_BACKEND_URL=$VITE_BACKEND_URL

COPY . .
RUN npm run build

# ---------------------------------------------------------------------------
# Stage 2 – serve with Caddy (auto-TLS, no manual cert management)
# ---------------------------------------------------------------------------
FROM caddy:2-alpine

# Caddyfile declares both the frontend site and the API reverse-proxy
COPY Caddyfile /etc/caddy/Caddyfile

# Copy built static files from the builder stage
COPY --from=builder /app/dist /srv/www

# 80  – HTTP (redirect to HTTPS)
# 443 – HTTPS
EXPOSE 80 443
