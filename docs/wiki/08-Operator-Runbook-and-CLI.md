# 🛠️ 08. Runbook оператора и CLI

[← Назад на Главную](Home)

---

## 1. Сводная таблица переменных окружения (`.env`)

| Переменная | По умолчанию | Описание |
|---|---|---|
| `NETWORK` | `Preprod` | Сеть Cardano (`Preprod` или `Mainnet`) |
| `BLOCKFROST_PROJECT_ID` | `preprodMoN7...` | API ключ Blockfrost для синхронизации блоков |
| `PAYMENT_SERVICE_URL` | `http://localhost:3001` | URL локальной ноды Masumi Payment Service |
| `PAYMENT_API_KEY` | `dev-token` | Секретный токен для авторизации запросов к ноде |
| `PAYMENT_MODE` | `off` | Режим платежей: `off` (симуляция) или `masumi` (реальный ончейн эскроу) |
| `POLICY_MONTHLY_LIMIT_LOVELACE` | `100000000` | Месячный лимит расходов (100 tADA) |
| `POLICY_MAX_PER_TASK_LOVELACE` | `10000000` | Лимит одной задачи (10 tADA) |
| `POLICY_HUMAN_APPROVAL_THRESHOLD_LOVELACE` | `4000000` | Порог обязательного ручного аппрува (4 tADA) |
| `POLICY_DB_PATH` | `buyer/state/policy.db` | Путь к базе данных идемпотентности и лимитов |

---

## 2. Команды управления

### 2.1. Полная комплексная проверка
```bash
./scripts/verify_all.sh
```

### 2.2. Запуск тестов
```bash
.venv/bin/pytest -v
```

### 2.3. Запуск линтера и статической типизации
```bash
.venv/bin/ruff check
.venv/bin/mypy common/ buyer/ seller/
```

### 2.4. Запуск сквозного демо
```bash
./scripts/run_demo.sh
```

### 2.5. Ручной запуск микросервисов в разных терминалах

**Терминал 1: Honest Продавец (ProÚčetní)**
```bash
FIRM_PROFILE=honest PORT=8003 PAYMENT_MODE=off .venv/bin/python -m seller.app
```

**Терминал 2: Sloppy Продавец (CheapBooks)**
```bash
FIRM_PROFILE=sloppy PORT=8002 PAYMENT_MODE=off .venv/bin/python -m seller.app
```

**Терминал 3: Дашборд покупателя**
```bash
PORT=8004 EVENTS_PATH=buyer/state/events.jsonl .venv/bin/python -m buyer.dashboard.app
```

**Терминал 4: Запуск оркестратора**
```bash
export SELLER_URLS="http://127.0.0.1:8002,http://127.0.0.1:8003"
.venv/bin/python -m buyer.orchestrator --scenario demo --pace 1.0
```
После запуска откройте дашборд в браузере: `http://localhost:8004`.
