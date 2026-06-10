---
example_id: PSC-01
churn_reason: price_sensitivity
channel: call
offer_id: PR-004
segment: standard
customer_signal: months_to_rate_reset=4, competitor_transfer_count=3
status: pass
violated_rules: []
---

# Call Script — Mortgage Loyalty Rate Review

**Call type:** Outbound retention — loyalty pricing
**Agent context:** Customer holds an active mortgage with fixed rate expiring in approximately 4 months.

---

**Opening (mandatory opt-out — CH-002):**

"Good morning, may I speak with Mr. Vermeersch? ... Hello, Mr. Vermeersch, this is Anouk calling from BankRetain's mortgage team. Before I go any further, I want to let you know that you can ask us at any time to stop contacting you about offers — just say the word and I'll update your preferences immediately. Are you happy for me to continue for just a moment? ... Thank you.

I'm calling today about your mortgage account — this is a loyalty call, not about any issue with your account."

---

**Pitch:**

"Your current fixed rate is due to expire in around four months, in October 2026. I wanted to reach out now, before the renewal window opens, to let you know about a loyalty pricing option we can offer you.

As an existing BankRetain mortgage customer, you're eligible for a loyalty rate review — which means we can offer you a reduction of up to 0.15% on your renewal fixed rate, with no arrangement fee and no property valuation required. That's available to you as a straight like-for-like renewal.

On a typical mortgage balance, a 0.15% rate reduction saves around €750 over a five-year fixed term — though your exact saving would depend on your remaining balance.

There's no obligation to decide today — I'd like to book a 20-minute callback with a mortgage specialist who can walk you through the exact numbers for your account. Would a time this week or next work for you?"

---

**Objection — 'I'm comparing rates elsewhere':**

"That's completely understandable, and I'd encourage you to compare. What I can tell you is that this loyalty pricing option isn't available on the open market — it's specifically for existing customers at renewal. It's worth having the numbers before you make any decision."

---

**Close:**

"I'll send you a confirmation of this call and the offer details by email. Is [customer email on file] the best address? ... Perfect. And again, if you'd prefer we don't contact you about future offers, just let me know and I'll note that now."
