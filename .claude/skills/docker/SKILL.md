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

## Заметки для Aiccountant007

Файла `rules/docker/dockerfile.mdc` в этом репозитории нет. Опирайся на чеклист выше, `infra/README.md`, `docs/ARCHITECTURE.md` (раздел о развёртывании) и задачу E1 в `docs/TASKS.md`. Если заметки расходятся с чеклистом, следуй заметкам.

- **Границы.** Контейнеризация — задача E1 (Эдуард). Dockerfile клади в `infra/`, `.dockerignore` — в корень репозитория. `seller/`, `buyer/`, `common/` и `pyproject.toml` ради Docker не трогай. Masumi Payment Service бери из `masumi-network/masumi-payment-service` как есть, на закреплённом теге или коммите. Его Dockerfile (`node:20-slim`) под этот чеклист не переписывай.
- **Образ наших сервисов.** Бери `python:3.11-slim`: в коде есть `enum.StrEnum`. Multi-stage не нужен, компилировать нечего. Лок-файла нет, источник зависимостей — `pyproject.toml`: сначала `COPY pyproject.toml` и `pip install --no-cache-dir ".[agents]"`, потом код. `requirements.txt` и локи poetry или uv не заводи.
- **Контекст сборки и `.dockerignore`.** Compose лежит в `infra/`, код в корне, поэтому `build: {context: .., dockerfile: infra/Dockerfile}`. Перенеси в `.dockerignore` из `.gitignore` секреты и runtime state: `.env.*`, `*.mnemonic`, `*.skey`, `*.sqlite*`, `*.db`, `events.jsonl`, `buyer/state/`, `seller/state/`, `.venv/`. Локальная `policy.sqlite` в образе даст в демо ложные `BLOCKED duplicate`. Не исключай `seller/tests/fixtures/` (из `a_mini.isdoc` строится `/example_output.json`, его URL уходит в реестр) и `data/` (демо-счета).
- **Запуск продавца.** `CMD ["python", "-m", "seller.app"]` из `WORKDIR=/app`: `main()` сам читает `PORT` и слушает `0.0.0.0`. Модульного `app` нет, только фабрика `create_app`, поэтому `uvicorn seller.app:app` упадёт; если нужен uvicorn, пиши `uvicorn --factory seller.app:create_app`. Один процесс, без `--workers` и gunicorn: jobs и ledger живут в памяти процесса. В slim-образе нет curl, поэтому healthcheck делай через `python -c` с urllib на `GET /availability` (порт бери из `os.environ['PORT']`). У payment-service проверяй `/api/v1/health` через `node -e` с fetch.
- **Переменные.** Секреты подключай через `env_file: ../.env`, не перечисляй ключи и мнемоники в `environment:`. В `environment:` переопредели то, что для двух продавцов разное или зависит от сети compose: у seller-honest и seller-sloppy свои `FIRM_PROFILE`, `PORT`, `FIRM_PRICE_LOVELACE`, `AGENT_IDENTIFIER`; плюс `PAYMENT_SERVICE_URL=http://masumi-payment-service:3001/api/v1`, `SELLER_URLS=http://seller-honest:8001,http://seller-sloppy:8002`, хост `postgres` в `DATABASE_URL`. Оба продавца собирай из одного образа. Подстановки `${VAR}` compose берёт из `.env` в `infra/`, а не из корня: запускай `docker compose --env-file ../.env up` и запиши эту команду в `infra/README.md`. `PAYMENT_MODE=masumi` в compose не хардкодь, пока не влит E3: без `seller/masumi_payment.py` `/start_job` отвечает 501, а `/availability` при этом 200, и healthcheck этого не заметит.
- **Состояние buyer.** Политика пишет SQLite по `POLICY_DB_PATH=buyer/state/policy.sqlite`. До `USER` выполни `mkdir -p buyer/state && chown <user> buyer/state` и смонтируй на `/app/buyer/state` named volume, иначе пересоздание контейнера обнулит идемпотентность и месячный лимит. Туда же направь `events.jsonl` (B6) и SQLite репутации (B4). Продавцов во время живой сделки на preprod не перезапускай: задача в памяти потеряется.
- **Что публиковать.** Наружу по HTTPS только продавцов: их `apiBaseUrl` идёт в реестр Masumi. Postgres на хост не публикуй. `masumi-payment-service` (:3001, кошельки и admin API) и `buyer` (:8000, дашборд с `POST /approve/{deal_id}`) публикуй только как `127.0.0.1:PORT:PORT`, дашборд открывай через SSH-туннель.
