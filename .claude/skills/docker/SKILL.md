---
name: docker
description: Apply Docker best practices when writing or reviewing a Dockerfile or Compose file — pinned slim base images, deterministic dependency installs, cache-friendly layer order, multi-stage builds, .dockerignore, non-root runtime, no secrets in image layers, exec-form CMD, healthchecks. Use whenever authoring or editing containerization for a project. Mirrors rules/docker/dockerfile.mdc.
---

# Docker

Claude-Code counterpart to `rules/docker/dockerfile.mdc`. Aim for images that are
small, reproducible, and secure.

## Checklist

**Base & reproducibility** — pin to a specific minor tag (`node:22-slim`), never `latest`; prefer slim/alpine/distroless. Install from lockfiles deterministically (`npm ci`, `pip install -r`, `poetry install`).

**Cache-friendly build** — copy dependency manifests and install BEFORE copying source, so code changes don't bust the deps layer. Use multi-stage builds: compile in a build stage, copy only the runtime artifact into a minimal final stage (no dev deps/build tools shipped). Add a `.dockerignore` (`.git`, `node_modules`, build output, `.env`). Combine related `RUN`s and clean caches in the same layer.

**Runtime security**
- Never run as root — create and `USER` a non-root user in the runtime stage.
- Never bake secrets into an image (no keys/tokens/`.env` in `COPY`/`ENV`); inject at runtime (env, mounted secrets, BuildKit `--secret`). Layers are cached and extractable.
- Exec-form `CMD`/`ENTRYPOINT` (`["node","server.js"]`) for signals; set `WORKDIR`; add a `HEALTHCHECK`; expose only needed ports.

**Compose** — keep env-specific values in `.env`/Compose env (don't commit real secrets); pin service images; `depends_on` with health conditions; named volumes for stateful services.

## How to use
When creating or editing a Dockerfile or Compose file, apply the checklist and read
`rules/docker/dockerfile.mdc` for the annotated examples. Cross-check secret handling
against the `web-security` skill.
