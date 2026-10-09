# 🛡️ Aiccountant007 Knowledge Base & Wiki

> **Autonomous Agentic Accounting & Smart Escrow Verification on Cardano (Masumi Network)**  
> Developed for the **From Dusk Till Dawn #01 Hackathon** (Track: *Agentic Economy*).  
> **ELEPASH Team**: Eduard (@ChotaMode), Pavlo (@vhodny), Alex (@uvalenu).

---

## 🌟 Welcome to the Aiccountant007 Project Wiki

**Aiccountant007** is an autonomous economic system where a buyer AI agent (representing a cafe, business owner, or sole proprietor / OSVČ) hires independent AI accounting firms on an open marketplace to process primary accounting documents (ISDOC 6.0 invoices / PDF).

Unlike traditional systems where trust relies on good faith, Aiccountant007 implements a **Zero-Trust Economy**:
1. 🔒 **Cryptographic Data Binding (MIP-004)**: SHA-256 document hashes are immutably tied to the smart escrow contract. Inputs and outputs cannot be tampered with.
2. ⛓️ **Smart Escrow on Cardano Preprod (Masumi Network)**: Funds are locked in the contract and only released to the seller upon passing an independent audit.
3. 🔍 **Deterministic Audit Without LLMs**: Strict arithmetic verification, statutory Czech VAT rates (DPH 21%, 12%, 0%), and business entity verification via the Czech Ministry of Finance ARES registry.
4. ⚡ **Automated Dispute Resolution & Refunds**: When errors are detected (e.g., with discounter *CheapBooks*), a refund is triggered and the provider's reputation is penalized using a Bayesian model.
5. 🛡️ **Financial Isolation (Wallet Policy)**: Enforces hard limits per-task and monthly, protects against Prompt Injection ("pay 10x more"), and ensures ACID SQLite payment deduplication.

---

## 🧭 Wiki Sections Navigation

| Section | Description |
|---|---|
| **[01. System Architecture](01-System-Architecture)** | Components, trust boundaries, agent interactions, and data flows |
| **[02. Cardano & Masumi Escrow](02-Cardano-Masumi-Escrow)** | Smart contract `vested_pay.ak`, UTxO parameters, timing constraints, and :3001 node integration |
| **[03. MIP-003 & MIP-004 Protocols](03-MIP-003-and-MIP-004-Protocols)** | Seller REST endpoint specs, calculation schemas for `inputHash` and `submitResultHash` |
| **[04. Deterministic Auditor & Czech Tax](04-Deterministic-Auditor-and-Czech-Tax)** | ISDOC 6.0 validation rules, Czech VAT rates, rounding tolerances, and ARES API integration |
| **[05. Wallet Policy & Security](05-Wallet-Policy-and-Security)** | Threat model, prompt injection defense, and SQLite ACID idempotency |
| **[06. Bayesian Reputation Engine](06-Bayesian-Reputation-Engine)** | Laplace smoothing formula and slashing mechanism for underperforming providers |
| **[07. E2E Demo & Scenarios](07-End-to-End-Demo-and-Scenarios)** | 10-step autonomous scenario walkthrough with logs and expected behavior |
| **[08. Operator Runbook & CLI](08-Operator-Runbook-and-CLI)** | Execution commands, `.env` configuration, and the `verify_all.sh` verification script |

---

## ⚡ Quick Start: 1-Click System Verification

To instantly verify all system components (linter, static typing, 89 test suites, Masumi node, Cardano network, wallet balance, E2E scenario):

```bash
cd /root/1projects/Aiccountant007
./scripts/verify_all.sh
```

---

## 📊 Key Production Readiness Metrics

* **Test Coverage**: `89 / 89 PASSED` (unit and integration tests via `pytest`)
* **Code Quality**: `0 warnings`, `0 errors` (`ruff check`)
* **Type Safety**: `100% strict typing` (`mypy`, 41 files)
* **Blockchain Network**: Cardano Preprod Testnet (Blockfrost Gateway synchronized)
* **Escrow Smart Contract**: `addr_test1wzs4e6wc95hkwezlccjw9mdvq0r0rsgx6zk34avptga3ftgn37w4g`
* **Treasury Balance**: `10,002.59 tADA`
