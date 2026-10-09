# 🌐 Masumi Network & Cardano Preprod Integration Guide

This guide details the end-to-end integration of **Aiccountant007** with the **Masumi Network** smart contract escrow on Cardano Preprod, from hot wallet seeding and MIP-003 agent registry to live escrow settlement and Sokosumi listing.

---

## 1. Architecture Overview

```
                      ┌───────────────────────────────────────┐
                      │        Sokosumi Marketplace /         │
                      │     External Autonomous Clients       │
                      └──────────────────┬────────────────────┘
                                         │ Job Dispatch / Payment
                                         ▼
┌───────────────────────┐      ┌─────────────────────────────┐
│   Buyer Dashboard /   │      │   Seller Agents (HTTP API)  │
│      Orchestrator     │      │   • ProÚčetní  (:8001 / https)│
│  (DeepSeek V3 Audit)  │      │   • CheapBooks (:8002 / https)│
└──────────┬────────────┘      └──────────────┬──────────────┘
           │ Lock Funds                       │ Submit Result / Dispute
           ▼                                  ▼
┌────────────────────────────────────────────────────────────┐
│         Masumi Payment Service Node (:3001)                │
│  • Swagger: http://127.0.0.1:3001/docs/                    │
│  • Hot Wallets: Purchasing & Selling                       │
└──────────────────────────┬─────────────────────────────────┘
                           │ Web3CardanoV2 Contract
                           ▼
┌────────────────────────────────────────────────────────────┐
│             Cardano Preprod Testnet Blockchain             │
│  • Escrow: addr_test1wzs4e6wc95hkwezlccjw9mdvq0r0rsgx6zk34 │
│  • Registry Policy: 67ab0c92c4ac1610895a1c965ee50aba41a8f │
└────────────────────────────────────────────────────────────┘
```

---

## 2. On-Chain Contracts & Wallets (Preprod)

| Component | Identifier / Address |
|---|---|
| **Cardano Network** | `Preprod` |
| **V2 Escrow Validator** | `addr_test1wzs4e6wc95hkwezlccjw9mdvq0r0rsgx6zk34avptga3ftgn37w4g` |
| **Registry Policy ID** | `67ab0c92c4ac1610895a1c965ee50aba41a8f1513b15240723b3bd0b` |
| **Purchasing Hot Wallet** | `addr_test1qppp8g8jfld3ztf9cw3sauf67kc87ev0g38nkzj8vtquy3cd2ysw0l6q64jrgtxkp0tp7mwldchajwm62gqjmzswuxqqfrjl02`<br>VKey: `4213a0f24fdb112d25c3a30ef13af5b07f658f444f3b0a4762c1c247` |
| **Selling Hot Wallet** | `addr_test1qzcm2see0ph2f4p793em0rfazdc764svmk7ffeevewl6dfd0kf53s49k25tcjehdw854r5ftglyug5zk2m87wxas6n3s7p9r9m`<br>VKey: `b1b54339786ea4d43e2c73b78d3d1371ed560cddbc94e72ccbbfa6a5` |
| **Team Faucet Wallet** | `addr_test1qpu552ygmh07sz7mcdvl7gcca5u6jswpuq92jk04w75ga3qvp2yenrqn90qpeh5rzj0gkdh75hl52yj2drfyclrur9qsst9h6j`<br>Balance: `10,002.58 tADA` |

---

## 3. Public Agent Endpoints

The seller agents are deployed behind Traefik reverse proxy with automatic TLS:

- **ProÚčetní (Honest Seller)**:
  - Base URL: `https://proucetni.tzhk.dev`
  - Availability probe: `https://proucetni.tzhk.dev/availability`
  - Fixed Fee: `5,000,000 Lovelace` (5.0 tADA)
  - Profile: Honest, full Czech VAT (21%, 12%, 0%) & ARES verification
- **CheapBooks (Sloppy Seller)**:
  - Base URL: `https://cheapbooks.tzhk.dev`
  - Availability probe: `https://cheapbooks.tzhk.dev/availability`
  - Fixed Fee: `2,000,000 Lovelace` (2.0 tADA)
  - Profile: Sloppy, miscalculates VAT (15% illegal rate) triggering dispute
- **Buyer Dashboard**:
  - URL: `https://aiccountant.tzhk.dev`

---

## 4. Quick Diagnostic Probe

Run the built-in diagnostic script to verify node health, hot wallets, balances, and public endpoints:

```bash
python3 scripts/masumi_check.py
```

Sample output:
```
============================================================
🔍 Masumi Node & Cardano Preprod Diagnostics
============================================================
Target URL: http://127.0.0.1:3001/api/v1
Network:    Preprod
Auth Token: configured (****)
------------------------------------------------------------
✅ 1. Masumi Node Health: ONLINE (200 OK)
✅ 2. Payment Sources: 1 source(s) configured
   • Type:    Web3CardanoV2 (Preprod)
   • Address: addr_test1wzs4e6wc95hkwezlccjw9mdvq0r0rsgx6zk34avptga3ftgn37w4g
   • Policy:  67ab0c92c4ac1610895a1c965ee50aba41a8f1513b15240723b3bd0b
✅ 3. Hot Wallets: 2 wallet(s) found
   • [Purchasing] Address: addr_test1qppp8...
   • [Selling]    Address: addr_test1qzcm2...
✅ 4. On-Chain Registry: 0 registered agent(s) found on Preprod
------------------------------------------------------------
5. Seller Honest (https://proucetni.tzhk.dev/availability): ONLINE (200)
   Seller Sloppy (https://cheapbooks.tzhk.dev/availability): ONLINE (200)
============================================================
```

---

## 5. Funding Hot Wallets

Before executing live on-chain registrations and escrows, transfer funds from the Team Faucet Wallet to the hot wallets:

1. **Selling Wallet** (`addr_test1qzcm2...`):
   - Needs: **15-20 tADA** (for minting registration NFT and submitting results).
2. **Purchasing Wallet** (`addr_test1qppp8...`):
   - Needs: **50-100 tADA** (for locking escrow contracts).

Send transactions via any Cardano Preprod wallet (e.g. Eternl, Lace, cardano-cli) or transfer using the faucet address.

---

## 6. Registering Agent in Masumi Registry (MIP-003)

Use `scripts/masumi_register.py` to register the seller agent on Cardano Preprod.

### 6.1. Preview Registration (Dry Run)
```bash
python3 scripts/masumi_register.py --profile honest
```

### 6.2. Submit Registration & Wait for On-Chain Minting
```bash
python3 scripts/masumi_register.py --profile honest --confirm --wait
```

The script sends `POST /api/v1/registry` to the node. The node mints a MIP-003 NFT with the agent metadata and returns an `agentIdentifier` (e.g., `<policyId>.<assetName>`).

Add the returned identifier to `.env`:
```env
AGENT_IDENTIFIER_HONEST=<minted_identifier>
```

Repeat for CheapBooks if desired:
```bash
python3 scripts/masumi_register.py --profile sloppy --confirm --wait
# Set AGENT_IDENTIFIER_SLOPPY=<minted_identifier>
```

---

## 7. Switching to Live Escrow Mode (`PAYMENT_MODE=masumi`)

### 7.1. Environment Configuration
Ensure `.env` contains:
```env
# Masumi Node
NETWORK=Preprod
PAYMENT_SERVICE_URL=http://localhost:3001/api/v1
PAYMENT_SERVICE_URL_DOCKER=http://host.docker.internal:3001/api/v1
PAYMENT_API_KEY=<your-masumi-token>
SELLER_PAYMENT_API_KEY=<your-masumi-token>
BUYER_PAYMENT_API_KEY=<your-masumi-token>

# Agent Identifiers
AGENT_IDENTIFIER_HONEST=<minted_identifier_honest>
AGENT_IDENTIFIER_SLOPPY=<minted_identifier_sloppy>

# Seller Mode
PAYMENT_MODE=masumi
SUPPORTED_PAYMENT_SOURCE_INDEX=0

# Buyer Security
DASHBOARD_ADMIN_TOKEN=<generate-random-secret>

# AI Auditor
OPENROUTER_API_KEY=<your-openrouter-key>
OPENROUTER_MODEL=deepseek/deepseek-chat
```

### 7.2. Smoke Test the Live Escrow Client
Before running orchestrations, test the buyer escrow client:
```bash
# Dry run verification
python3 -m buyer.purchase --smoke

# Live testnet transaction check (requires funded purchasing wallet)
python3 -m buyer.purchase --smoke --confirm
```

### 7.3. Launch Container Stack
```bash
docker compose up -d
```

The dashboard will display:
```
LIVE ESCROW (Preprod)
```
with human-approval guards requiring `X-Admin-Token` for transactions exceeding safety thresholds.

---

## 8. Listing on Sokosumi Marketplace

Once the agent is registered in the Masumi Registry, list it on the [Sokosumi Marketplace](https://app.sokosumi.com) (Preprod: `https://api.preprod.sokosumi.com/v1`):

1. **Agent Endpoint**: `https://proucetni.tzhk.dev`
2. **Category**: Forensic Accounting / Document Analysis
3. **Capability**: `DeepSeek-V3-VAT-Audit` (v1.0.0)
4. **Input Schema**:
   ```json
   {
     "type": "object",
     "properties": {
       "documents": {
         "type": "array",
         "items": { "type": "string" },
         "description": "Base64-encoded ISDOC or PDF invoices"
       }
     },
     "required": ["documents"]
   }
   ```
5. **Pricing**: 5.00 tADA (`5,000,000` lovelace) fixed pricing via Web3CardanoV2 contract.
6. **Agent Identifier**: Use `AGENT_IDENTIFIER_HONEST`.
