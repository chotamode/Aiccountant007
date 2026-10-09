# 🛠️ 08. Operator Runbook & CLI

[← Back to Home](Home)

---

## 1. Environment Variables Reference (`.env`)

| Variable | Default | Description |
|---|---|---|
| `NETWORK` | `Preprod` | Cardano network (`Preprod` or `Mainnet`) |
| `BLOCKFROST_PROJECT_ID` | `<your-blockfrost-key>` | Blockfrost API key for block synchronization |
| `PAYMENT_SERVICE_URL` | `http://localhost:3001` | URL of the local Masumi Payment Service node |
| `PAYMENT_API_KEY` | `dev-token` | Secret bearer token for authorizing requests to the node |
| `PAYMENT_MODE` | `off` | Payment mode: `off` (simulation) or `masumi` (live on-chain escrow) |
| `POLICY_MONTHLY_LIMIT_LOVELACE` | `100000000` | Monthly spending cap (100 tADA) |
| `POLICY_MAX_PER_TASK_LOVELACE` | `10000000` | Per-task spending limit (10 tADA) |
| `POLICY_HUMAN_APPROVAL_THRESHOLD_LOVELACE` | `4000000` | Threshold requiring manual operator approval (4 tADA) |
| `POLICY_DB_PATH` | `buyer/state/policy.db` | Path to the idempotency and policy SQLite database |

---

## 2. Operational Commands

### 2.1. Comprehensive System Verification
```bash
./scripts/verify_all.sh
```

### 2.2. Running Test Suites
```bash
.venv/bin/pytest -v
```

### 2.3. Running Linter & Static Type Checking
```bash
.venv/bin/ruff check
.venv/bin/mypy common/ buyer/ seller/
```

### 2.4. Running the End-to-End Demo
```bash
./scripts/run_demo.sh
```

### 2.5. Manually Running Microservices Across Terminals

**Terminal 1: Honest Seller (ProÚčetní)**
```bash
FIRM_PROFILE=honest PORT=8003 PAYMENT_MODE=off .venv/bin/python -m seller.app
```

**Terminal 2: Sloppy Seller (CheapBooks)**
```bash
FIRM_PROFILE=sloppy PORT=8002 PAYMENT_MODE=off .venv/bin/python -m seller.app
```

**Terminal 3: Buyer Dashboard**
```bash
PORT=8004 EVENTS_PATH=buyer/state/events.jsonl .venv/bin/python -m buyer.dashboard.app
```

**Terminal 4: Running the Orchestrator**
```bash
export SELLER_URLS="http://127.0.0.1:8002,http://127.0.0.1:8003"
.venv/bin/python -m buyer.orchestrator --scenario demo --pace 1.0
```
After starting services, open the operator console in your browser: `http://localhost:8004`.
