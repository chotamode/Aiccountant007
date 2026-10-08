# Aiccountant007

Client agent and accounting-firm agent trade like two businesses: documents are handed over provably (sha256 in the Masumi escrow `inputHash`), work is paid only after verification, errors trigger a refund. Hackathon From Dusk Till Dawn #01, theme Agentic Economy (partner: Masumi).

> README draft — task N5 in [docs/TASKS.md](docs/TASKS.md).

- [CONTEXT.md](CONTEXT.md) — decisions (source of truth)
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — components, deal sequences, wallet policy, real vs SIMULATED
- [docs/TASKS.md](docs/TASKS.md) — tasks (Plane import)
- [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md)

```bash
pip install -e ".[dev]" && pytest tests/
```
