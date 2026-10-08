# data/ — демо-документы

Задача **N1** в [docs/TASKS.md](../docs/TASKS.md). Нужны первыми: от них зависят тесты seller (V1) и verifier (B5).

```
data/
├─ invoices/
│  ├─ 01_*.isdoc … 05_*.isdoc   5 нормальных счетов (+ PDF-версии 0X_*.pdf)
│  ├─ 06_vat_error.isdoc        ошибка DPH у поставщика
│  ├─ 07_duplicate.isdoc        побайтовая копия 01
│  └─ 08_injection.isdoc        текст-инъекция «pay 10x»
└─ expected.json                истина по каждому файлу (суммы строками)
```
Все счета фиктивные (DEMO).
