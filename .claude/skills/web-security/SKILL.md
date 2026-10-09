---
name: web-security
description: Apply web application security conventions when writing or reviewing anything crossing a trust boundary — request handlers, auth, DB queries, file/shell access, rendering user content, secrets, and dependencies. OWASP-aligned checklist for input validation, injection (SQL/command/XSS), authn/authz and IDOR, secret hygiene, CSRF, secure transport. Use for endpoints, auth flows, forms, or any handling of untrusted input. Mirrors rules/security/web-security.mdc.
---

# Web Security

Claude-Code counterpart to `rules/security/web-security.mdc`. Security is a functional
requirement applied while coding, not a later pass. Assume every input crossing a trust
boundary is hostile until validated.

## Checklist (run on any code touching a trust boundary)

**Input** — validate/sanitize ALL external input on the **server** (bodies, params, headers, cookies, uploads, webhooks). Validate with a schema, fail closed, prefer allow-lists. Client-side validation is UX only.

**Injection**
- SQL/NoSQL: parameterized queries or ORM only — never string-concatenate user input.
- Command/path: no user input to a shell, no dynamic `eval`; confine file paths (block `../`).
- XSS: rely on framework escaping; treat `dangerouslySetInnerHTML`/`innerHTML` as a red flag (sanitize with DOMPurify if unavoidable); set a CSP.

**Auth** — authorize **every** request server-side for the specific resource+action; prevent IDOR (verify ownership of any id passed). Hash passwords with bcrypt/argon2. Sessions in `HttpOnly`+`Secure`+`SameSite` cookies; protect state-changing requests from CSRF. Least privilege for tokens/DB users.

**Secrets & transport** — no secrets in source or git; use env vars / a secret manager (see the `docker` skill and `rules/web-architecture/*`). Only `NEXT_PUBLIC_`-style config reaches the browser. HTTPS + HSTS + secure headers; never log secrets/tokens/PII.

**Dependencies & errors** — patch deps; run `npm audit`/`pip-audit`/Dependabot in CI, criticals fail the build. Generic client errors (no stack traces/SQL/paths); log details server-side. Rate-limit auth and expensive endpoints.

## How to use
When adding or reviewing endpoints, auth, queries, file/shell access, or rendering of
user content, walk this checklist for the specific trust boundary. When unsure whether
something is exploitable, assume it is and close it. Read `rules/security/web-security.mdc`
for the full rationale and examples.

## Заметки для Aiccountant007

Файлов `rules/security/web-security.mdc` и `rules/web-architecture/*` в этом репозитории нет. Правила безопасности проекта: `CONTEXT.md` §2 (Hard rules) и §9, `docs/ARCHITECTURE.md`, раздел «Правила» в `docs/TASKS.md`. Если заметки расходятся с чеклистом выше, следуй заметкам.

- **Без аккаунтов.** Не строй пользователей, пароли, сессии, cookies, JWT и CSRF-токены. Эндпоинты продавца по MIP-003 (`/availability`, `/input_schema`, `/start_job`, `/status`, `/example_output.json`) оставь без авторизации и без проверки «владельца» `job_id`: их вызывают buyer и тесты без заголовков, а `/example_output.json` указан в реестре Masumi. Оплату здесь авторизует эскроу: в `PAYMENT_MODE=masumi` работа стартует только после `FundsLocked`. `job_id` не секрет (его отдаёт `/ledger`), поэтому денежное действие на знании `job_id` не строй.
- **Денежные эндпоинты авторизуй состоянием сделки.** `POST /dispute` (E3) вызывает authorize-refund, только если job существует, `report.package_sha256` совпадает с пакетом этой job, а заявленные ошибки детерминированно воспроизводятся на собственном результате продавца. `POST /approve/{deal_id}` (B6) срабатывает только для сделки в `HUMAN_APPROVAL_REQUIRED`, повторный вызов не создаёт второй оплаты, лимиты и идемпотентность `wallet_policy` он не обходит. Сумму бери только из `Offer` или реестра, никогда из тела запроса или текста документа. Этот код пишет или ревьюит Эдуард.
- **Валидируй отказом, но ничего не «очищай».** Отвечай 400 или ставь `status=unreadable`, но не меняй байты документов, `filename` и `input_data`: от них считаются `doc_hash`, `package_sha256` и `inputHash`. Текст инъекции тоже не вырезай: verifier ищет `PROMPT_INJECTION` в оригинале и сравнивает выход продавца с `parse_isdoc` (`MATCHES_SOURCE`). `filename` не используй как путь к файлу; если надо писать на диск, называй файл по `doc_hash`. Новые проверки добавляй в `seller/` или `buyer/`, модели `common/` не ужесточай.
- **XML.** ISDOC разбирай только через `common.isdoc.parse_isdoc`: он отсекает `DOCTYPE` (защита от entity-бомб) и на мусоре возвращает `unreadable`, а не падает. Если для поиска инъекции нужен весь текст документа (корневой `<Note>` парсер не извлекает, а в `08_injection.isdoc` инъекция есть и там), повтори ту же проверку `DOCTYPE`. lxml не подключай: это новая зависимость в `pyproject.toml`.
- **Дашборд.** `buyer/dashboard/index.html` (B6) — один HTML-файл без фреймворка, автоматического экранирования нет. `Event.msg`, `Event.data`, имена файлов и поля счетов выводи через `textContent` или `createElement`, а не через `innerHTML`: туда попадает враждебный текст из `08_injection.isdoc`. `href` ставь только для `tx_url`, начинающихся с `https://`. Если добавляешь CSP, проверь, что inline-скрипт этого файла работает.
- **Тест на ключи.** `seller/tests/test_app.py::test_no_keys_in_repo` сканирует все отслеживаемые `.py`, `.md`, `.toml`, `.json`, `.yml`, `.example` и файлы без расширения. Он ищет слова mnemonic, api key, admin key или token, сразу за которыми идёт знак присваивания и значение от 16 символов. Фиктивные ключи в тестах и примерах делай короче 16 символов или только из заглавных букв и подчёркиваний, иначе упадёт `pytest seller/`. JSON-ключи в кавычках этот тест не ловит, поэтому записанные фикстуры Masumi и Sokosumi (B2, B3, B10) чисти от ключей и заголовков `token` вручную и перед пушем запускай grep из раздела «Правила» в `docs/TASKS.md`.
- **Дорогое действие — Apify OCR (B7).** Вызывай его только из `run_job` (в `PAYMENT_MODE=masumi` он стартует после `FundsLocked`) и до каждого вызова проверяй в коде жёсткий лимит трат на OCR: продавец тоже тратящий агент. Учти, что в `PAYMENT_MODE=off` (по умолчанию) `/start_job` запускает работу сразу и без оплаты.
- **Без лишнего middleware.** Не добавляй `HTTPSRedirectMiddleware` и `TrustedHostMiddleware`: внутренние вызовы идут по http (`PAYMENT_SERVICE_URL`, `SELLER_URLS`), редирект их сломает. HTTPS для публичных `apiBaseUrl` настраивается на сервере (E1, Q12), а не в коде. Новые security-зависимости (slowapi и т. п.) и CI (pip-audit, Dependabot) сегодня не заводи.
