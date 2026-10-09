# ⛓️ 02. Cardano & Masumi Escrow

[← Back to Home](Home)

---

## 1. Escrow Smart Contract (Aiken Validator)

Payments are governed by Masumi Network's open-source **V2 Escrow Validator** smart contract, written in **Aiken** (`masumi-network/masumi-payment-service/smart-contracts/payment/validators/vested_pay.ak`).

* **Cardano Preprod Script Address**:  
  [`addr_test1wzs4e6wc95hkwezlccjw9mdvq0r0rsgx6zk34avptga3ftgn37w4g`](https://preprod.cardanoscan.io/address/addr_test1wzs4e6wc95hkwezlccjw9mdvq0r0rsgx6zk34avptga3ftgn37w4g)
* **Registry Policy ID**:  
  `67ab0c92c4ac1610895a1c965ee50aba41a8f1513b15240723b3bd0b`

---

## 2. On-Chain UTxO Datum Structure

Each escrow transaction represents a UTxO output with the following state (Datum):

```rust
type Datum {
  purchaser: VerificationKeyHash,
  seller: VerificationKeyHash,
  input_hash: ByteArray,             // SHA-256 hash of the input package
  result_hash: Option<ByteArray>,    // SHA-256 hash of the seller result
  pay_by_time: Int,                  // Payment deadline
  submit_result_time: Int,           // Result submission deadline
  unlock_time: Int,                  // Funds withdrawal unlock time
  external_dispute_unlock_time: Int, // External arbitration unlock time
  state: EscrowState,                // FundsLocked | ResultSubmitted | Disputed | RefundRequested | Withdrawn
}
```

---

## 3. Deal Lifetimes and Timing Constraints

The validator code and `masumi-payment-service` node enforce strict transaction timing constraints:

| Parameter | Masumi Code Constraint | Aiccountant007 Demo Value |
|---|---|---|
| `payByTime` | $\ge \text{now} - 5\text{ min}$ and $\le \text{submitResultTime} - 5\text{ min}$ | $+10\text{ min}$ from start |
| `submitResultTime` | $\ge \text{now} + 15\text{ min}$ | $+20\text{ min}$ from start |
| `unlockTime` | $\ge \text{submitResultTime} + 15\text{ min}$ | $+40\text{ min}$ from start |
| `externalDisputeUnlockTime` | $\ge \text{unlockTime} + 15\text{ min}$ | $+60\text{ min}$ from start |

### Smart Contract Refund Mechanics:

1. **If result was NOT submitted by seller**:
   The buyer can execute `WithdrawRefund` immediately after `submitResultTime` passes.
2. **If result WAS submitted by seller (`ResultSubmitted`)**:
   A refund request (`POST /purchase/request-refund`) transitions the smart contract to the **`Disputed`** state.
   For the buyer to reclaim funds (`RefundWithdrawn`), the seller must confirm the validity of the dispute via the **`AuthorizeRefund`** operation.
3. **If seller ignores the dispute**:
   After `externalDisputeUnlockTime` elapses, the dispute can be resolved manually by the Masumi admin committee (2-of-3 multisig).

---

## 4. Masumi Payment Service Node (`localhost:3001`)

The node runs locally on port `3001` and connects to PostgreSQL `aicc-postgres` (143 applied migrations) and the Blockfrost gateway.

* **Swagger Documentation**: `http://localhost:3001/docs/`
* **Buyer Wallet**: `addr_test1qppp8g8jfld3ztf9cw3sauf67kc87ev0g38nkzj8vtquy3cd2ysw0l6q64jrgtxkp0tp7mwldchajwm62gqjmzswuxqqfrjl02`
* **Seller Wallet**: `addr_test1qzcm2see0ph2f4p793em0rfazdc764svmk7ffeevewl6dfd0kf53s49k25tcjehdw854r5ftglyug5zk2m87wxas6n3s7p9r9m`
* **Team Treasury Wallet**: `addr_test1qpu552ygmh07sz7mcdvl7gcca5u6jswpuq92jk04w75ga3qvp2yenrqn90qpeh5rzj0gkdh75hl52yj2drfyclrur9qsst9h6j` (balance: **10,002.59 tADA**)
