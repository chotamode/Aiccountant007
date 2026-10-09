# Handoff: доделать реальный эскроу Masumi

Сейчас весь продукт работает в режиме SIMULATED: ни одной реальной транзакции через Masumi не было. Этот файл — задание для любого агента (Claude Code, Antigravity), если доработку надо продолжить без исходной сессии. Правила проекта — в `AGENTS.md`, скиллы — в `.claude/skills/`.

## Почему Masumi не работает

1. Ноды нет ни в одном compose. `PAYMENT_SERVICE_URL=http://masumi-payment-service:3001` указывает на несуществующий хост.
2. `PAYMENT_API_KEY`, `AGENT_IDENTIFIER` и `NETWORK` не передаются в контейнеры. У buyer нет ключа, поэтому `real_escrow=None` и сделка всегда SIMULATED.
3. `/dispute` у продавца вызывает authorize-refund сразу, до состояния `Disputed`, поэтому возврат на реальной ноде сломается.
4. Ошибки ноды превращаются в голый 500. Сбой submit-result теряется, а результат уже отдан покупателю.
5. `docs/RUNLOG.md` §2 и песочница лендинга выдают симуляцию за реальные транзакции.

## Общий контракт (все части должны ему следовать)

- **C1 Продавец, env:** `PAYMENT_MODE` (off|masumi), `PAYMENT_SERVICE_URL`, `PAYMENT_API_KEY`, `NETWORK` (Preprod), `AGENT_IDENTIFIER`, `SUPPORTED_PAYMENT_SOURCE_INDEX` (0). В режиме masumi `create_app()` падает на старте, если нет URL, ключа или `AGENT_IDENTIFIER`.
- **C2 Продавец, `POST /dispute`:** вход `{job_id, report}`, ответ `{"authorized": bool, "pending": bool, "reason": str}`. 404 — нет job, 409 — job не завершена. Отказ, если `report.package_sha256` не совпадает с пакетом job или заявленные ошибки не воспроизводятся. Идемпотентен. В режиме off подтверждённые ошибки дают `authorized=true` сразу. В режиме masumi: если нода уже в `Disputed`, вызвать authorize-refund с повторами; иначе фоновый поток одобрит, когда станет можно, а ответ — `pending=true`. Отвечает не дольше ~10 с.
- **C3 Покупатель, возврат:** проверка не прошла → request_refund (до `unlockTime`) → ждать `Disputed` (или `RefundRequested`, если результата нет) → `/dispute` → принято, если `authorized` или `pending` → при `--refund-timeout > 0` ждать `RefundWithdrawn`, иначе честно `REFUND_PENDING`. Если результата нет вовсе, всё равно request_refund до `unlockTime`. В реальном режиме отказываться платить по `SIMULATED-…` blockchainIdentifier.
- **C4 Покупатель:** реальный режим — когда заданы и `PAYMENT_SERVICE_URL`, и `PAYMENT_API_KEY`. Атрибут `buyer.real_mode` нужен дашборду.
- **C5 Дашборд:** env `DASHBOARD_ADMIN_TOKEN`. В реальном режиме `POST /api/run-scenario` и `POST /approve/{deal_id}` требуют заголовок `X-Admin-Token`, сравнение через `hmac.compare_digest`. Без заданного токена — 403. `GET /api/mode` → `{"real": bool, "network": str}`. Бейдж SIMULATED показывать в симуляции, «live escrow» — только в реальном режиме. Никакого `innerHTML` для данных событий.
- **C6 Compose** (корневой `docker-compose.yml` основной): продавцы — `AGENT_IDENTIFIER=${AGENT_IDENTIFIER_HONEST:-}` / `${AGENT_IDENTIFIER_SLOPPY:-}`, `PAYMENT_API_KEY=${SELLER_PAYMENT_API_KEY:-}`. buyer — `PAYMENT_API_KEY=${BUYER_PAYMENT_API_KEY:-}`, `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `DASHBOARD_ADMIN_TOKEN`. У всех трёх `PAYMENT_SERVICE_URL=${PAYMENT_SERVICE_URL_DOCKER:-http://host.docker.internal:3001/api/v1}`, `extra_hosts: ["host.docker.internal:host-gateway"]`, `NETWORK=${NETWORK:-Preprod}`. `env_file` со всем `.env` не использовать: там мнемоники кошельков.

## Задачи (каждую в своей ветке от `Ed`)

1. **Продавец** (`seller/app.py`, `seller/masumi_payment.py`, `seller/tests/`): C1, C2. Ошибки ноды → 502 с текстом от ноды. `wait_funds_locked` повторяет запрос при сетевых сбоях. Результат не показывать в `/status`, пока submit-result не прошёл; submit-result повторять до `submitResultTime` минус запас. Тесты — с фейковой нодой.
2. **Покупатель** (`buyer/purchase.py`, `buyer/orchestrator.py`, тесты): C3, C4. `wait_state` терпит временные ошибки. Таймауты считать от времён продавца. Сверять сумму блокировки с одобренной политикой. Добавить `python -m buyer.purchase --smoke`: реальная покупка только с флагом `--confirm`.
3. **Дашборд** (`buyer/dashboard/*`): C5. В реальном режиме `policy.sqlite` не пересоздавать на каждый клик. Одновременно только один сценарий (409). Убрать XSS.
4. **Инфраструктура и документы:** C6, новые переменные в `.env.example`, `docker compose config -q`. Пометить SIMULATED в RUNLOG §2 и на лендинге. Убрать префикс ключа Blockfrost из wiki 08. `scripts/deploy_wiki.sh` не должен печатать токен. Скрипты `scripts/masumi_check.py` и `scripts/masumi_register.py`. Runbook `docs/MASUMI_INTEGRATION.md`.

Точные поля API брать из исходников `masumi-network/masumi-payment-service` (`src/routes/api/...`) и из swagger своей ноды (`:3001/docs`).
