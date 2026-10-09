# 🎬 07. E2E Demo & Scenarios

[← Back to Home](Home)

---

## 1. End-to-End 10-Step Scenario (`scripts/run_demo.sh`)

The demo scenario showcases the complete lifecycle of autonomous economic interactions between the client and accounting services.

### Step 1. Invoice Package Hashing
* Invoice documents are scanned by `buyer/vault.py`.
* Individual SHA-256 hashes and the composite `package_sha256` are computed.

### Step 2. Discovery & Provider Selection
* The orchestrator queries the marketplace catalog:
  * *CheapBooks*: 2.0 tADA (reputation 0.50);
  * *ProÚčetní*: 5.0 tADA (reputation 0.50).
* The lowest-priced eligible provider is selected: **CheapBooks**.

### Step 3. Escrow Lock
* Via `POST /purchase`, 2,000,000 lovelace are locked in the smart contract.
* An on-chain transaction link appears in the Cardano Preprod Explorer.

### Step 4. Auditor Detects Errors
* CheapBooks submits the parsed invoice data.
* The deterministic verifier identifies the illegal 15% VAT rate on two line items. Status: `VERIFICATION_FAILED`.

### Step 5. Automated Dispute Resolution
* The discrepancy report is submitted to `POST /dispute`.
* CheapBooks acknowledges the discrepancies and authorizes a full refund.

### Step 6. Reputation Slashing
* CheapBooks' reputation drops to $0.33$, landing the firm on the blacklist.

### Step 7. Defeating Prompt Injection
* Document `08_injection.isdoc` attempts to demand 10x the agreed tariff (20 tADA instead of 2 tADA).
* `WalletPolicy` blocks the attempt with code `BLOCKED_PRICE_MISMATCH`.

### Step 8. Hiring a Reliable Provider
* Package #2 is routed to **ProÚčetní**.
* All audits pass (VAT 21%/12%/0%, math checks out, entities verified in ARES).
* Escrow funds are released to ProÚčetní.

### Step 9. Preventing Duplicate Payments
* Re-submission of Package #2 is blocked by `WalletPolicy` based on hash matching (`BLOCKED_DUPLICATE`).

### Step 10. Rescuing the Initial Package
* Package #1, previously refunded by CheapBooks, is re-routed to ProÚčetní and completed successfully.
