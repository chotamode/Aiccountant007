# Aiccountant007 — правила для ИИ-агентов

Два агента торгуют как два бизнеса: `buyer/` (агент клиента) покупает обработку счетов у `seller/` (агент бухгалтерской фирмы, профили honest «ProÚčetní» и sloppy «CheapBooks»). Оплата идёт через эскроу Masumi на Cardano preprod. Подробности: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), тексты задач — [docs/TASKS.md](docs/TASKS.md), нерешённое — [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md). Исполнители, зависимости и статусы задач — в Plane (workspace `hackaton`, проект Aicountant).

## Как работать

- Одна задача = одна ветка `feat/<id>` от `Ed` = один worktree. Не трогай файлы вне своей задачи.
- Задача готова, когда тест из пункта «Готово, когда» в `docs/TASKS.md` зелёный и запушен в ветку задачи.
- `common/` — контракт обеих сторон. Модели бери оттуда (`from common import ...`, хэши — `from common.hashing import ...`). Менять `common/` и `pyproject.toml` можно только через Эдуарда: в этих файлах параллельные ветки конфликтуют.
- Код с деньгами (`buyer/purchase.py`, `buyer/wallet_policy.py`, `seller/masumi_payment.py`) пишет или ревьюит только Эдуард.

## Скиллы проекта

В `.claude/skills/` лежат скиллы, по которым пишется код этого проекта. Claude Code подгружает их сам. Агенты на других инструментах перед началом работы читают нужный `SKILL.md` вручную.

| Скилл | Когда применять |
|---|---|
| [typed-python](.claude/skills/typed-python/SKILL.md) | любая правка `.py` |
| [web-security](.claude/skills/web-security/SKILL.md) | эндпоинты FastAPI, разбор чужих данных (ISDOC, ответы продавца и ноды), вызовы Masumi и Sokosumi, ключи |
| [docker](.claude/skills/docker/SKILL.md) | `infra/`, Dockerfile, docker compose |

Файлы `rules/*.mdc`, на которые ссылаются скиллы, в этом репозитории не лежат: хватает чеклиста из самого скилла. В конце каждого скилла есть раздел «Заметки для Aiccountant007». Если он расходится с общим чеклистом, следуй заметкам.

## Жёсткие правила

- Деньги — `Decimal` (в JSON строкой) или целые lovelace. `float` не использовать: разъедутся хэши и суммы.
- Хэши считать только через `common.hashing`. Результат продавца — только `JobResult.to_result_string()`: от этой строки считается `outputHash`.
- Всё, что не прошло через testnet или sandbox, помечать `simulated=True` (в ленте появится бейдж SIMULATED). Выдавать замоканный платёж за настоящий нельзя.
- Секреты (мнемоники, API-ключи, токены) только в `.env` на сервере. В коде, логах, Plane и коммитах их быть не должно.
- Перед пушем: `pytest` зелёный и `git diff --cached | grep -iE "mnemonic|api_key|token=|secret"` пусто.
