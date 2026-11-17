# syntax=docker/dockerfile:1
# Multi-stage Dockerfile for MassCommAI React/Vite Frontend

# Stage 1: Build production assets
FROM node:20-alpine AS builder

WORKDIR /app

# Copy dependency specifications first to maximize layer cache
COPY package.json package-lock.json ./
RUN npm ci

# Copy application source code
COPY . .

# Build production bundle (outputs to /app/dist)
RUN npm run build

# Stage 2: Serve static assets via lightweight NGINX
FROM nginx:alpine AS runner

# Remove default nginx website configuration
RUN rm -rf /etc/nginx/conf.d/*

# Copy custom NGINX configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy bundled production assets from builder
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost/healthz || exit 1

CMD ["nginx", "-g", "daemon off;"]
