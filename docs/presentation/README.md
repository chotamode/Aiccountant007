# Aiccountant007 Pitch Deck & Presentation

Hackathon: **From Dusk Till Dawn #01**  
Track: **Agentic Economy (Partner: Masumi Network)**  
Team: **ELEPASH** (Eduard, Pavlo, Alex)

---

## 📄 Formats Available

1. **PDF Slides**: [`Aiccountant007_Presentation.pdf`](Aiccountant007_Presentation.pdf) (10 slides, 1920x1080, print/judge ready)
2. **Interactive HTML Viewer**: [`index.html`](index.html) (Keyboard navigation `←` `→`, fullscreen `f`)
3. **High-Res PNG Slides**:
   - [Slide 1: Title & Overview](slides/slide_01.png)
   - [Slide 2: Problem Statement](slides/slide_02.png)
   - [Slide 3: The 3-Layer Solution](slides/slide_03.png)
   - [Slide 4: Autonomous Buyer Agent Lifecycle](slides/slide_04.png)
   - [Slide 5: Independent Verifier & Injection Defense](slides/slide_05.png)
   - [Slide 6: Autonomous Dispute Resolution & Reputation](slides/slide_06.png)
   - [Slide 7: Live SSE Dashboard & Human Approval](slides/slide_07.png)
   - [Slide 8: Code Quality & Engineering Standards](slides/slide_08.png)
   - [Slide 9: Architectural Truth Matrix](slides/slide_09.png)
   - [Slide 10: Conclusion & Submission Links](slides/slide_10.png)

---

## 🎯 Slide Breakdown & Speaker Notes

### Slide 1: Welcome & Value Proposition
- **Headline**: Autonomous B2B Accounting, Independent Auditing & Smart Escrow on Cardano.
- **Key point**: Traditional accounting software trusts inputs and humans. In the agentic economy, AI agents must transact with unfamiliar seller agents while protecting their capital.

### Slide 2: The Agentic Trust Deficit
- **Key point**: 4 core failure modes:
  1. Pre-payment rug pulls (seller vanishes).
  2. Prompt injection theft (attacker injects instructions to pay 10x).
  3. LLM hallucinations (bad tax rates like 15% instead of 21%/12%).
  4. Sybil attacks & repeat offenders.

### Slide 3: The Solution Architecture
- **Layer 1: Cryptographic Escrow**: MIP-004 cryptographic binding linking documents via SHA-256 to Cardano smart escrow.
- **Layer 2: Independent Verifier**: Deterministic mathematical and regulatory checks (ISDOC 6.0, Czech VAT, ARES registry).
- **Layer 3: Deterministic Wallet Policy**: ACID SQLite engine enforcing idempotency and preventing budget breaches.

### Slide 4: Autonomous Buyer Lifecycle
- **Step-by-step**: Discovery → Selection → Policy Pre-flight → Escrow Lock → Processing → Independent Audit → Payment Release or Dispute.

### Slide 5: Independent Verifier
- **Auditing**: Math line integrity, legal Czech VAT rates (21%, 12%, 0%), vendor validation via ARES, and prompt injection filtering.

### Slide 6: Dispute Resolution & Slashing
- **SLA Enforcement**: When CheapBooks submits invalid 15% VAT, verifier rejects it, calls seller `POST /dispute`, automatically authorizes on-chain refund, and slashes seller Bayesian reputation from 0.50 down to 0.33.

### Slide 7: Real-Time Telemetry
- **Dashboard**: Live Server-Sent Events (SSE) feed, clickable CardanoScan links, one-click human approval for transactions over threshold.

### Slide 8: Production Engineering
- **Quality**: 88/88 pytest tests passing, 0 ruff linter errors, 0 mypy type errors, complete Docker compose infrastructure.

### Slide 9: Architectural Truth Matrix
- **Honest Engineering**:
  - MIP-004 hash binding: **REAL**
  - Accounting verifier: **REAL**
  - Wallet policy: **REAL**
  - Bayesian reputation engine: **REAL**
  - Automated SLA dispute: **REAL**
  - Masumi Cardano escrow: **REAL / READY**
  - Masumi admin escalation: **NOT AUTOMATED (External)**

### Slide 10: Conclusion & Next Steps
- Full links to repository and video presentation. Ready for hackathon evaluation.
