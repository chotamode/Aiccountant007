# START — ветка `Pash`

Работаешь автономно в ветке `Pash`; потом Эдуард сливает её с `Ed`. Твои задачи: **V1** (seller/) и, если успеешь, **V2/B5** (verifier). Полный текст задач с критериями «готово, когда» — в [TASKS.md](TASKS.md).

## Прочитать за 5 минут
1. [CONTEXT.md](../CONTEXT.md) §6 и §11 — что делает seller.
2. [ARCHITECTURE.md](ARCHITECTURE.md) §2 — контракты `common/`.
3. `common/mip003.py` (`JobInput`, `JobResult`, `INPUT_SCHEMA`), `common/invoice.py`, `common/ledger.py`.

## Старт
```bash
git checkout Pash
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[agents,dev]"
pytest tests/          # контракты: 8 passed
```

## Что делать по порядку
1. `common/isdoc.py`: `parse_isdoc(bytes) -> ExtractedInvoice`. Пока нет `data/`, сделай 1–2 своих ISDOC в `seller/tests/fixtures/`.
2. `seller/processing.py` + `seller/profiles.py`: чистая функция без сети. Правило sloppy описано в V1 (первые 2 документа с 21% → 15%, без случайности).
3. `seller/app.py`: эндпоинты MIP-003 + `/ledger`. По умолчанию `PAYMENT_MODE=off` (SIMULATED).
4. Тесты `pytest seller/` по пунктам 1–5 из V1.
5. Когда появится `data/` (N1): прогнать honest и sloppy против `data/expected.json`.

## Нельзя
- Писать логику покупки, оплаты и возврата: это E3/E5 (Эдуард). Оставь в коде `TODO(E3)` там, где нужна оплата.
- Менять `common/` без договорённости. Если нужно новое поле, напиши Эдуарду: это контракт для обеих сторон.
- Коммитить `.env` и ключи.

## Перед уходом (~22:15)
`git push origin Pash` и комментарий к V1 в Plane: что готово, где остановился, какие тесты красные.
