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
