# 📜 03. MIP-003 & MIP-004 Protocols

[← Back to Home](Home)

---

## 1. MIP-003: Agent Service Interaction Standard

The **MIP-003** protocol defines the standard HTTP REST API that an agent service offering capabilities in the Masumi ecosystem must expose.

In Aiccountant007, an accounting agent implements the following endpoints:

### 1.1. `GET /availability`
Checks service availability and retrieves cryptographic identifiers and pricing.
* **Response**:
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
Initializes processing of a document package and creates an escrow payment request.
* **Request Body**:
```json
{
  "identifier_from_purchaser": "deal-8a9f2b1c",
  "input_data": {
    "package_sha256": "630d0fae...",
    "documents_json": "[{\"filename\": \"inv_01.isdoc\", \"content_base64\": \"...\"}]"
  }
}
```
* **Response**:
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
Checks job execution status and fetches the output.
* **Response (when completed)**:
```json
{
  "status": "completed",
  "result": "{\"invoices\": [...]}",
  "submit_result_hash": "e5f6a7b8..."
}
```

### 1.4. `POST /dispute` *(Aiccountant007 Extension)*
Automated dispute resolution for quality discrepancies.
* **Request Body**: `VerificationReport` detailing detected VAT or arithmetic discrepancies.
* **Seller Behavior**: The service deterministically re-verifies its output. If the discrepancy is confirmed, it invokes `POST /payment/authorize-refund` on the Masumi node.

---

## 2. MIP-004: Hashing and Proof Specification

The **MIP-004** protocol guarantees that funds are escrowed strictly against a specific set of input bytes.

Hashing formulas (`common/hashing.py`):

1. **Individual Document Hash**:
   $$\text{doc\_hash} = \text{SHA256}(\text{bytes})$$

2. **Package Hash (`package_sha256`)**:
   $$\text{package\_sha256} = \text{SHA256}\left(\bigoplus_{i} \text{sorted}(\text{doc\_hash}_i)\right)$$

3. **Masumi Input Hash (`inputHash`)**:
   $$\text{inputHash} = \text{SHA256}(\text{purchaserId} + \text{";"} + \text{canonicalJSON}(\text{input\_data}))$$

4. **Masumi Output Hash (`outputHash`)**:
   $$\text{outputHash} = \text{SHA256}(\text{purchaserId} + \text{";"} + \text{json\_escape}(\text{result}))$$

> [!NOTE]
> `package_sha256` is embedded inside `input_data`, ensuring the Cardano smart contract's on-chain datum simultaneously validates the transmission of each individual document.
