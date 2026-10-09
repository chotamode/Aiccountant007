# 📊 06. Bayesian Reputation (Slashing)

[← Back to Home](Home)

---

## 1. Why Bayesian Evaluation?

A naive success ratio $\frac{\text{successful}}{\text{total}}$ suffers from the "cold start problem":
* A new agent with 1 successful job out of 1 would receive a $100\%$ ($1.0$) score, outpacing an established firm with $99$ successes out of $100$ ($0.99$).
* A new agent with 1 initial failure would drop to $0\%$, with no opportunity to recover.

**Aiccountant007** utilizes a Beta prior distribution with Laplace smoothing:

$$\text{Score} = \frac{\text{Successful Deals} + 1}{\text{Total Deals} + 2}$$

---

## 2. Rating Dynamics in Production

* **Initial State (New Agents)**:
  $$\text{Score} = \frac{0 + 1}{0 + 2} = 0.50$$
* **Selection Threshold (`REPUTATION_THRESHOLD`)**: `0.40`. A new agent is eligible to participate in marketplace dispatch.

### CheapBooks Case Study (Sloppy Execution & Slashing):
1. Start: $0/0 \to 0.50$ (passes threshold).
2. Invalid VAT detected on the very first order:
   $$\text{Score} = \frac{0 + 1}{1 + 2} = 0.333$$
3. Score $0.333 < 0.40$ $\implies$ **automatically blacklisted and excluded from the provider pool**.

### ProÚčetní Case Study (Reliability & Growth):
1. Start: $0/0 \to 0.50$.
2. Successful completion of the first package:
   $$\text{Score} = \frac{1 + 1}{1 + 2} = 0.667$$
3. Successful completion of the second package:
   $$\text{Score} = \frac{2 + 1}{2 + 2} = 0.750$$
4. Confidence solidifies, giving the agent priority selection when prices are tied.
