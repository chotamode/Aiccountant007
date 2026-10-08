# START — ветка `Ed`

Эдуард: деньги, нода, интеграция. Задачи **E1–E8**; после ухода ребят ещё **B1–B10** через ИИ-агентов (каждая в своём worktree от `Ed`). Полный текст — [TASKS.md](TASKS.md). Нерешённое — [OPEN_QUESTIONS.md](../OPEN_QUESTIONS.md), сначала Q1, Q2, Q3.

## Старт
```bash
git checkout Ed
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[agents,dev]"
pytest tests/          # 8 passed
cp .env.example .env   # заполнить, не коммитить
```

## Параллельные агенты (worktree от Ed)
```bash
git worktree add ../wt-e4 -b feat/e4-wallet-policy Ed
git worktree add ../wt-b1 -b feat/b1-vault Ed
git worktree add ../wt-b4 -b feat/b4-reputation Ed
git worktree add ../wt-b6 -b feat/b6-dashboard Ed
```
Сразу можно запускать без зависимостей: **E4, B4, B6**, а также B1 и B2 на фикстурах (живые данные после N1 и E6). Промпт агенту: «Выполни задачу <ID> из docs/TASKS.md. Используй только модели из common/. Готово, когда тест из пункта “Готово, когда” зелёный. Не трогай файлы вне своей задачи».

## Контрольные точки
23:00 первая tx (E2) · 01:00 happy path · 03:00 возврат + второй продавец · 05:00 лимит, дубликат, атака, лента · 06:00 стоп фич.

## Слияние с Pash
`git merge Pash` в `Ed`. Конфликты возможны только в `common/` (менять его только через Эдуарда) и в `pyproject.toml`.
