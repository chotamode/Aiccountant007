---
name: typed-python
description: Apply strict typed-Python conventions when writing, refactoring, or reviewing Python code — mandatory and maximally specific type hints, deliberate data structures (dataclass/NamedTuple/TypedDict/Enum), exceptions over sentinel values, layered architecture with Protocol interfaces, pytest testing, and mypy/pyright static analysis. Use whenever the task involves writing or changing .py files, or the user asks about Python typing, structure, or code quality. Mirrors the Cursor rules in this repo (rules/python/*.mdc).
---

# Typed Python

The Claude-Code counterpart to this repo's Cursor rules (`rules/python/*.mdc`), so
Python written here — by Cursor or by Claude — follows one standard. When editing
Python, apply the checklist below; open the matching `.mdc` for the full rationale.

## Guiding principle
Catch bugs in the editor or the static analyzer, never in runtime by users. The cost
of a bug grows with the stage it's caught at: editor < CI < runtime. Types + static
analysis + tests push detection as early as possible.

## Checklist (apply on every Python change)

**Type hints** — see `rules/python/type-hints.mdc`
- Annotate every function: all parameters and the return type, private helpers included.
- Most specific type possible: never bare `dict`/`list`/`Any`; parametrize (`list[User]`, `dict[str, float]`).
- Python 3.10+ syntax: `int | str`, `X | None` — not `Optional`/`Union`.
- `Literal[...]` for fixed value sets; `TypeAlias` when a name should carry domain meaning (`Celsius`, `Phone`).
- In signatures prefer abstract containers (`Iterable`, `Sequence`, `Mapping`) over concrete `list`/`dict`.

**Data structures** — see `rules/python/data-structures.mdc`
- Default record: `@dataclass(slots=True, frozen=True)`. `NamedTuple` when it must unpack; `TypedDict` for dict-style/JSON; `Enum` for closed value sets.
- Never pass bare tuples or loose dicts between layers.

**Errors** — see `rules/python/errors.mdc`
- Exceptional paths raise exceptions — never return `None`/`False`/`0` to signal failure.
- Define domain exceptions in `exceptions.py`; translate low-level errors (`ValueError`, `URLError`, `JSONDecodeError`, `KeyError`) into them at the boundary.
- The caller (entry point) decides what to do with a failure.

**Architecture** — see `rules/python/architecture.mdc`
- One responsibility per module; weak coupling; entry point only orchestrates typed functions.
- Replaceable components are `typing.Protocol` interfaces (structural, checked statically), passed in via dependency injection — prefer over `abc.ABC`.
- Many small verb-named functions; classes only when they add real value. Config in a config module; secrets in env vars.

**Testing** — see `rules/python/testing.mdc`
- `pytest`, mirrored under `tests/`, one behavior per test, `parametrize` over duplication.
- Test the exceptional path (`pytest.raises(DomainError)`). Inject hand-written fakes that satisfy the `Protocol`; mock only true I/O edges. Never hit the real network.

**Tooling** — see `rules/python/tooling.mdc`
- Code must pass `mypy`/`pyright` cleanly. No `# type: ignore` without an explanation comment.
- Format with `ruff format`/`black`, lint with `ruff` (see `rules/python/code-style.mdc`). Type check and tests run in CI and block merge.

## How to use this skill
1. Skim the checklist and read the specific `.mdc` file(s) relevant to the change.
2. Write or refactor the code to satisfy them.
3. Before finishing, self-review: every function typed? right data structure? exceptions not sentinels? passes a mental mypy? tests cover the failure path?

## Заметки для Aiccountant007

Файлов `rules/python/*.mdc` в этом репозитории нет, хватает чеклиста выше. Если заметки ниже расходятся с ним, следуй заметкам. Общие правила проекта лежат в `AGENTS.md`.

- **Модели — pydantic, а не dataclass.** Всё, что уходит в JSON, HTTP, `Event` или SQLite либо разбирает ответы Masumi и Sokosumi, бери из `common/`. Недостающие локальные модели делай на `pydantic.BaseModel`, как `StartJobRequest` и `_Job` в `seller/app.py` или `FirmProfile` в `seller/profiles.py`. Сериализуй через `model_dump(mode="json")` или `model_dump_json()`, тогда `Decimal` уйдёт строкой. `@dataclass` оставь для внутренних значений, которые никуда не сериализуются. Закрытые множества значений — `StrEnum`, как в `common/`.
- **Ожидаемые бизнес-исходы — данные, а не исключения.** Отказ политики: `Decision(status=BLOCKED, reason=...)`. Проваленная проверка: `Check(passed=False)`. Ошибка поставщика в исходнике (06): `Check(severity=WARNING)`. Недоступный ARES: `Check(simulated=True)`. Нечитаемый документ: `ExtractedInvoice(status=UNREADABLE)`. В тестах проверяй `status`, `passed` и `severity`, а не `pytest.raises`. Исключения оставь для сбоев (сеть, нода, невалидный вход) и переводи их на границе: в эндпоинте в `HTTPException`, в фоновой задаче в `JobStatus.FAILED` с `error`, как в `seller/app.py`.
- **Без общих файлов по шаблону.** Не создавай `buyer/exceptions.py`, `buyer/config.py`, `buyer/types.py`, `buyer/tests/conftest.py`. Задачи идут параллельно в разных worktree, и одноимённые файлы дадут конфликт add/add. Исключения, `TypeAlias` и чтение env держи в модуле своей задачи (например, `class VaultError(Exception)` в `buyer/vault.py`), фикстуры клади в свой тестовый файл. Переменные окружения называй так, как в `.env.example`, без синонимов.
- **Инструменты.** Конфигов mypy и ruff и CI в проекте нет. Не добавляй их в `pyproject.toml` и не заводи CI. Не запускай `ruff format`, `black` или `ruff check --fix` на весь репозиторий: перепишутся чужие файлы, в том числе `common/`. Линтер и mypy запускай только на своих файлах. Ошибка mypy `Unexpected keyword argument "blockchainIdentifier" for "StartJobResponse"` ложная: алиасы заданы через `AliasChoices`, а pydantic-плагина нет. Создавай модель через `StartJobResponse.model_validate(raw)` или с аргументами в snake_case.
- **Где тесты.** Тест клади по пути из «Готово, когда» (`buyer/tests/test_vault.py` и т. п.), иначе — в `buyer/tests/test_<модуль>.py`. Не зеркаль в `tests/buyer/`: команда приёмки такой тест не найдёт. Корневой `tests/` оставь для контрактных тестов `common/`.
- **Интерфейсы из TASKS.md буквально.** Сигнатуры из раздела «Выход» в `docs/TASKS.md` (`check(...) -> Decision`, `score(seller_id) -> float`, `Protocol SellerAdapter`, `build_job_input(docs) -> JobInput`) — точки стыковки задач в E7. Реализуй их как написано. `input_data` передавай ровно тем `dict[str, str]`, который вернул `JobInput.to_input_data()`, не заворачивай и не пересобирай: от него считается `inputHash`.
- **Сеть в тестах.** Юнит-тесты без сети: записанные фикстуры в `buyer/tests/fixtures/*.json`, ARES замокан. B3 тестируй против настоящего `seller.app` через `TestClient` с `PAYMENT_MODE=off`. Живые проверки из «Готово, когда» (E3 и E5 на preprod, smoke B2, B7 с реальной ценой Apify, B10 на Sokosumi) моками не заменяй. Делай их отдельной CLI-командой (например, `python -m buyer.purchase --smoke`) или тестом со `skipif`, если нужного ключа нет в env.
