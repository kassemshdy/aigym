# Build stage — node 22 matches the local toolchain
FROM node:22-alpine AS build

ENV NPM_CONFIG_UPDATE_NOTIFIER=false
ENV NPM_CONFIG_FUND=false

# Vite bakes import.meta.env.VITE_* in at build time, not runtime — a plain
# service variable doesn't reach this build stage on its own, so it has to
# be declared as a build ARG and re-exported as an ENV before `npm run
# build` runs. Railway passes matching service variables as build args
# automatically; unset (mock mode) is the correct default when it isn't.
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . ./
RUN npm run build

# Serve stage — caddy only, no node process at runtime
FROM caddy:2-alpine

WORKDIR /app
COPY Caddyfile ./
RUN caddy fmt Caddyfile --overwrite
COPY --from=build /app/dist ./dist

CMD ["caddy", "run", "--config", "Caddyfile", "--adapter", "caddyfile"]
