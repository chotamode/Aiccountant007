# Hackathon HQ Submission: Aiccountant007

### Project Name
**Aiccountant007**

### One-liner
Autonomous client agent that hires accounting firms on Masumi, locks escrow on Cardano, audits extracted invoices independently, and automatically triggers refunds and reputation penalties for bad work.

### Theme & Partner Tracks
* **Primary Track**: Agentic Economy
* **Partner Bounty**: Masumi Network (Autonomous B2B agent commerce & smart contract escrow)
* **Audio Track**: Best ElevenLabs Use (Dynamic synthetic auditor narration for video presentation and dashboard alerts)

### Description (under 1000 characters)
In the agentic economy, AI agents must trade services with economic accountability. Today, pre-paying external agents risks non-delivery, prompt injections threaten to drain wallets, and duplicate bills go unnoticed.

Aiccountant007 demonstrates verifiable B2B agentic commerce:
1. Cryptographic binding: invoice packages are hashed (sha256) into Masumi's on-chain inputHash.
2. Smart escrow: funds are locked in contract escrow before any work starts.
3. Hard wallet policies: strict monthly limits, per-task caps, human approval thresholds, and byte-level duplicate invoice blocking.
4. Independent client auditor: validates math, Czech VAT rates (21%/12%/0%), ARES business registries, and neutralizes prompt injections.
5. Automated dispute protocol: bad work generates a cryptographic verification report, triggering an automated refund from the escrow and reducing seller reputation.

### Links
* **Repository**: https://github.com/chotamode/Aiccountant007
* **Demo Video (90s)**: [docs/video/Aiccountant007_Demo_90s.mp4](docs/video/Aiccountant007_Demo_90s.mp4)
* **Pitch Deck (PDF)**: [docs/presentation/Aiccountant007_Presentation.pdf](docs/presentation/Aiccountant007_Presentation.pdf)
* **Cardano Preprod Run Log**: [docs/RUNLOG.md](docs/RUNLOG.md)
