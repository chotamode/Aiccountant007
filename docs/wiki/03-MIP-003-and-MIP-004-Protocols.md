# 📜 03. Протоколы MIP-003 & MIP-004

[← Назад на Главную](Home)

---

## 1. MIP-003: Стандарт взаимодействия с сервисом агента

Протокол **MIP-003** определяет стандартный HTTP REST API, который обязан предоставлять сервис, предлагающий услуги в экосистеме Masumi.

В проекте Aiccountant007 агент-бухгалтер реализует следующий набор методов:

### 1.1. `GET /availability`
Проверка готовности сервиса и получение криптографических реквизитов.
* **Ответ**:
```json
{
  "status": "available",
  "agent_id": "pro-ucetni-cz",
  "seller_vkey": "ed25519_pk1...",
  "pricing": {
    "amount": "5000000",
    "unit": "lovelace"
  }
}
```

### 1.2. `POST /start_job`
Инициализация обработки пакета документов и создание платежного требования.
* **Тело запроса**:
```json
{
  "identifier_from_purchaser": "deal-8a9f2b1c",
  "input_data": {
    "package_sha256": "630d0fae...",
    "documents_json": "[{\"filename\": \"inv_01.isdoc\", \"content_base64\": \"...\"}]"
  }
}
```
* **Ответ**:
```json
{
  "job_id": "job-381029",
  "blockchain_identifier": "bc-pay-9921",
  "input_hash": "a1b2c3d4...",
  "pay_by_time": "2026-10-09T03:45:00.000Z",
  "submit_result_time": "2026-10-09T04:00:00.000Z",
  "unlock_time": "2026-10-09T04:20:00.000Z",
  "external_dispute_unlock_time": "2026-10-09T04:40:00.000Z"
}
```

### 1.3. `GET /status?job_id={id}`
Проверка статуса обработки и получение результата.
* **Ответ (когда готово)**:
```json
{
  "status": "completed",
  "result": "{\"invoices\": [...]}",
  "submit_result_hash": "e5f6a7b8..."
}
```

### 1.4. `POST /dispute` *(Расширение Aiccountant007)*
Автоматическое урегулирование претензий по качеству.
* **Тело запроса**: `VerificationReport` с детальным описанием найденных расхождений в НДС или арифметике.
* **Поведение продавца**: Сервис детерминированно перепроверяет свои выходные данные. Если ошибка подтверждается, вызывает `POST /payment/authorize-refund` на ноде Masumi.

---

## 2. MIP-004: Спецификация хэширования и доказательств

Протокол **MIP-004** гарантирует, что средства блокируются под конкретный набор байтов задачи.

Формулы хэширования (`common/hashing.py`):

1. **Хэш каждого документа**:
   $$\text{doc\_hash} = \text{SHA256}(\text{bytes})$$

2. **Пакетный хэш (`package_sha256`)**:
   $$\text{package\_sha256} = \text{SHA256}\left(\bigoplus_{i} \text{sorted}(\text{doc\_hash}_i)\right)$$

3. **Входной хэш Masumi (`inputHash`)**:
   $$\text{inputHash} = \text{SHA256}(\text{purchaserId} + \text{";"} + \text{canonicalJSON}(\text{input\_data}))$$

4. **Выходной хэш Masumi (`outputHash`)**:
   $$\text{outputHash} = \text{SHA256}(\text{purchaserId} + \text{";"} + \text{json\_escape}(\text{result}))$$

> [!NOTE]
> `package_sha256` зашит внутрь `input_data`, поэтому смарт-контракт Cardano своим ончейн-датумом одновременно подтверждает и факт передачи каждого индивидуального документа.
