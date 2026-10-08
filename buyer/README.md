# buyer/ — агент клиента + dashboard

Задачи: E4, E5, E7 (Эдуард), B1–B6, B10 в [docs/TASKS.md](../docs/TASKS.md).

```
buyer/
├─ discovery.py        B2: реестр Masumi + Sokosumi → Offer[], выбор по цене и репутации
├─ seller_adapter.py   B3: Mip003Adapter (наши фирмы), SokosumiAdapter (внешний агент)
├─ wallet_policy.py    E4: лимиты в коде, порог человека, идемпотентность (SQLite)
├─ vault.py            B1: sha256 документов, хэш пакета
├─ purchase.py         E5: POST /purchase, ожидание состояний, request-refund
├─ verifier.py         B5: суммы, DPH 21/12%, сверка с ISDOC, ARES, дубликаты, инъекции
├─ reputation.py       B4: оценка продавца по исходам (SQLite)
├─ orchestrator.py     E7: весь сценарий
├─ events_bus.py       B6: publish/subscribe событий common.Event
├─ dashboard/          B6: index.html (лента, бейдж SIMULATED, tx-ссылки, Approve)
└─ tests/
```
