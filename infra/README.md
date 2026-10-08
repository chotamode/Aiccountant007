# infra/ — сервер, Masumi-нода, docker compose

Задачи **E1, E2, E6** в [docs/TASKS.md](../docs/TASKS.md). Подробности: [docs/ARCHITECTURE.md §8](../docs/ARCHITECTURE.md).

- `docker-compose.yml`: postgres + masumi-payment-service (:3001) + seller-honest (:8001) + seller-sloppy (:8002) + buyer (:8000).
- Payment Service: `masumi-network/masumi-payment-service` (Dockerfile на `node:20-slim`, swagger на `/docs`).
- Сначала `docker manifest inspect <image>`: если arm64 нет, используем VPS (x86, Coolify), а не Oracle ARM.
- Oracle: открыть порты в Security List **и** в iptables.
- Секреты только в `.env` на сервере.
