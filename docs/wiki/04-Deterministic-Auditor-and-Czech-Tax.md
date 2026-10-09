# 🔍 04. Deterministic Auditor (DPH/ARES)

[← Back to Home](Home)

---

## 1. Why Deterministic Audit?

Using an LLM to verify the work of another LLM creates a second-order failure problem:
* The second model can hallucinate just as the first one did;
* Verification becomes probabilistic and non-deterministic;
* High inference cost and latency.

In **Aiccountant007**, the auditor (`buyer/verifier.py`) is written in strict Python using exact `Decimal` arithmetic and contains zero LLM calls.

---

## 2. Czech Accounting Standards & ISDOC 6.0

The auditor verifies extracted data against the Czech Republic national standard **ISDOC 6.0** (electronic invoicing XML specification):

### 2.1. Value-Added Tax (DPH) Rates
The Czech Republic statutory framework defines strict VAT rates:
* **21%** — Standard rate (most goods and services);
* **12%** — Reduced rate (food, pharmaceuticals, public transport — in effect since the 2024 tax reform);
* **0%** — Exempt supplies (exports, financial services).

> [!WARNING]
> The former **15%** rate was abolished. Discounter *CheapBooks* deliberately uses 15% on certain invoices, which instantly triggers a `CheckCode.VAT_RATE_ALLOWED` audit violation.

### 2.2. Mathematical Precision of Line Items and Rounding
For each invoice line item, equality is verified:
$$\text{line\_total} = \text{quantity} \times \text{unit\_price}$$
Tax amount:
$$\text{vat\_amount} = \text{taxable\_base} \times \frac{\text{vat\_rate}}{100}$$

The grand total is checked against the legally permitted rounding tolerance ($\le 1.00\text{ CZK}$):
$$|\text{total\_with\_vat} - (\text{total\_without\_vat} + \text{total\_vat})| \le 1.00$$

---

## 3. Integration with the State Registry ARES

The verifier validates the counterparty business identification number (IČO):
* Check digit validation (weighted modulo 11 algorithm);
* Query to the free public REST API of **ARES** (Czech Ministry of Finance):
  `https://ares.gov.cz/ekonomicke-subjekty-v-be/rest/ekonomicke-subjekty/{ico}`
* Cross-checking the official company name and registered office address.
