# ⛓️ 02. Cardano & Masumi Escrow

[← Назад на Главную](Home)

---

## 1. Смарт-контракт эскроу (Aiken Validator)

В основе платежей лежит открытый смарт-контракт **V2 Escrow Validator** сети Masumi, написанный на языке **Aiken** (`masumi-network/masumi-payment-service/smart-contracts/payment/validators/vested_pay.ak`).

* **Адрес скрипта на Cardano Preprod**:  
  [`addr_test1wzs4e6wc95hkwezlccjw9mdvq0r0rsgx6zk34avptga3ftgn37w4g`](https://preprod.cardanoscan.io/address/addr_test1wzs4e6wc95hkwezlccjw9mdvq0r0rsgx6zk34avptga3ftgn37w4g)
* **Policy ID Реестра**:  
  `67ab0c92c4ac1610895a1c965ee50aba41a8f1513b15240723b3bd0b`

---

## 2. Структура ончейн-датума (UTxO Datum)

Каждая сделка в эскроу представляет собой выход UTxO со следующим состоянием (Datum):

```rust
type Datum {
  purchaser: VerificationKeyHash,
  seller: VerificationKeyHash,
  input_hash: ByteArray,             // sha256 хэш входного пакета
  result_hash: Option<ByteArray>,    // sha256 хэш результата от продавца
  pay_by_time: Int,                  // дедлайн на оплату
  submit_result_time: Int,           // дедлайн сдачи результата
  unlock_time: Int,                  // время разблокировки вывода средств
  external_dispute_unlock_time: Int, // время разблокировки внешнего арбитража
  state: EscrowState,                // FundsLocked | ResultSubmitted | Disputed | RefundRequested | Withdrawn
}
```

---

## 3. Временные рамки и тайминги сделки

Код валидатора и ноды `masumi-payment-service` предъявляет жесткие требования к таймингам транзакций:

| Параметр | Ограничение в коде Masumi | Значение в демо Aiccountant007 |
|---|---|---|
| `payByTime` | $\ge \text{now} - 5\text{ мин}$ и $\le \text{submitResultTime} - 5\text{ мин}$ | $+10\text{ мин}$ от старта |
| `submitResultTime` | $\ge \text{now} + 15\text{ мин}$ | $+20\text{ мин}$ от старта |
| `unlockTime` | $\ge \text{submitResultTime} + 15\text{ мин}$ | $+40\text{ мин}$ от старта |
| `externalDisputeUnlockTime` | $\ge \text{unlockTime} + 15\text{ мин}$ | $+60\text{ мин}$ от старта |

### Особенности возврата средств в смарт-контракте:

1. **Если результат НЕ был отправлен продавцом**:
   Покупатель может выполнить операцию `WithdrawRefund` сразу после наступления `submitResultTime`.
2. **Если результат БЫЛ отправлен продавцом (`ResultSubmitted`)**:
   Запрос на возврат (`POST /purchase/request-refund`) переводит смарт-контракт в состояние **`Disputed`**.
   Чтобы покупатель смог забрать средства (`RefundWithdrawn`), продавец должен подтвердить обоснованность претензии через операцию **`AuthorizeRefund`**.
3. **Если продавец игнорирует спор**:
   После наступления `externalDisputeUnlockTime` спор может быть разрешен вручную комитетом администраторов Masumi (мультиподпись 2 из 3).

---

## 4. Нода Masumi Payment Service (`localhost:3001`)

Нода запущена локально на порту `3001` и подключена к базе данных PostgreSQL `aicc-postgres` (143 примененные миграции) и шлюзу Blockfrost.

* **Swagger-документация**: `http://localhost:3001/docs/`
* **Кошелек покупателя**: `addr_test1qppp8g8jfld3ztf9cw3sauf67kc87ev0g38nkzj8vtquy3cd2ysw0l6q64jrgtxkp0tp7mwldchajwm62gqjmzswuxqqfrjl02`
* **Кошелек продавца**: `addr_test1qzcm2see0ph2f4p793em0rfazdc764svmk7ffeevewl6dfd0kf53s49k25tcjehdw854r5ftglyug5zk2m87wxas6n3s7p9r9m`
* **Кошелек фонда команды**: `addr_test1qpu552ygmh07sz7mcdvl7gcca5u6jswpuq92jk04w75ga3qvp2yenrqn90qpeh5rzj0gkdh75hl52yj2drfyclrur9qsst9h6j` (баланс: **10,002.59 tADA**)
