# seller/ — агент бухгалтерской фирмы (MIP-003)

Задача: **V1** в [docs/TASKS.md](../docs/TASKS.md). Оплата и возврат на стороне продавца: **E3** (Эдуард).

```
seller/
├─ app.py              FastAPI: /availability /input_schema /start_job /status /ledger /example_output.json (+ /dispute из E3)
├─ processing.py       process(JobInput, FirmProfile) -> (JobResult, [LedgerEntry])  — без сети
├─ profiles.py         honest = ProÚčetní, sloppy = CheapBooks (детерминированно портит DPH в 2 док.)
├─ masumi_payment.py   E3: POST /payment с короткими таймингами, submit-result, authorize-refund
├─ ocr.py              B7: PDF → Apify OCR (опционально)
└─ tests/
common/isdoc.py        parse_isdoc(bytes) -> ExtractedInvoice  (общий для seller и verifier)
```

Запуск (когда будет код):
```
FIRM_PROFILE=honest PORT=8001 PAYMENT_MODE=off python -m seller.app
FIRM_PROFILE=sloppy PORT=8002 PAYMENT_MODE=off python -m seller.app
```
