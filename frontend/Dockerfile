# syntax=docker/dockerfile:1
#
# The Syntitude web front — the Vue app built once, then served by nginx with the API proxied
# beside it. Built by `compose.yaml` at the repo root; the context is `frontend/`.
#
# Two build args, and they are the ONLY place a deployment's paths enter the bundle
# (`vite.config.ts`, `src/api/request.ts`):
#   VITE_PUBLIC_BASE    where the app is served from — `/` or e.g. `/syntitude/`, slash-bounded
#   VITE_API_BASE_URL   where the API lives — empty means "under the app's own base"
#                       (`${VITE_PUBLIC_BASE}api/v1`), which the nginx stage below proxies. Set it
#                       only when the API moves to another origin, e.g. the later public deployment.

# ── build ────────────────────────────────────────────────────────────────────────────────────────
# Node 24 is the active LTS; `package-lock.json` is lockfileVersion 3, which any npm ≥ 7 accepts.
FROM node:24-bookworm-slim AS build
WORKDIR /srv/syntitude/frontend

# Dependencies first, so a source edit does not reinstall them.
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY . .

ARG VITE_PUBLIC_BASE=/
ARG VITE_API_BASE_URL=

# ⛔ Two ways an empty or malformed argument would build a bundle that loads and then fails quietly:
#  - an EMPTY `VITE_API_BASE_URL` reaches the client as `""`, not as undefined, and `?? "/api/v1"`
#    does not replace an empty string — every request becomes relative to whatever page is open.
#    So it is never left empty: it is derived from the base instead.
#  - a base without its slashes makes asset URLs that resolve against the wrong directory. So it is
#    checked here and the build fails, naming the value.
RUN set -eu; \
    case "$VITE_PUBLIC_BASE" in \
      /|/*/) ;; \
      *) echo "VITE_PUBLIC_BASE must begin and end with '/' (got '$VITE_PUBLIC_BASE')" >&2; exit 1 ;; \
    esac; \
    if [ -z "$VITE_API_BASE_URL" ]; then VITE_API_BASE_URL="${VITE_PUBLIC_BASE}api/v1"; fi; \
    export VITE_API_BASE_URL; \
    echo "building for base '$VITE_PUBLIC_BASE', API at '$VITE_API_BASE_URL'"; \
    npm run build

# ── serve ────────────────────────────────────────────────────────────────────────────────────────
FROM nginx:1.30-alpine

ARG VITE_PUBLIC_BASE=/

# nginx's own welcome page would otherwise answer at `/` whenever the app lives under a subpath.
RUN rm -f /etc/nginx/conf.d/default.conf /usr/share/nginx/html/index.html /usr/share/nginx/html/50x.html

COPY nginx/syntitude.conf.template /etc/nginx/syntitude.conf.template
RUN sed "s#@PUBLIC_BASE@#${VITE_PUBLIC_BASE}#g" /etc/nginx/syntitude.conf.template \
      > /etc/nginx/conf.d/syntitude.conf \
    && nginx -t

# The bundle lands AT the base, so a URL path maps onto a file path with no rewriting at all.
COPY --from=build /srv/syntitude/frontend/dist /usr/share/nginx/html${VITE_PUBLIC_BASE}

# Read by the compose healthcheck, so it probes the path this image actually serves.
ENV SYNTITUDE_PUBLIC_BASE=${VITE_PUBLIC_BASE}
