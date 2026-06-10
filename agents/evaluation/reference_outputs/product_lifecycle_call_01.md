---
example_id: PLC-01
churn_reason: product_lifecycle
channel: call
offer_id: PR-016
segment: standard
customer_signal: months_to_rate_reset=3, competitor_transfer_count=4, mortgage_balance_eur=180000
status: pass
violated_rules: []
---

# Call Script — Mortgage Refinance Review

**Call type:** Outbound retention — product lifecycle
**Agent context:** Mortgage expires in 3 months; customer has been transferring to competitors.

---

**Opening (mandatory opt-out — CH-002):**

"Good morning, may I speak with Ms. Leclercq? ... Hello Ms. Leclercq, this is Wout calling from BankRetain's mortgage team. Before I go on — you can ask us to stop contacting you about offers at any time and I'll action that immediately. May I continue for just a moment? ... Thank you.

I'm calling about your mortgage account — this is a loyalty call, not about any issue."

---

**Pitch:**

"Your current fixed rate is due to expire in around three months, in September 2026. We'd like to offer you a no-obligation 30-minute refinancing review with one of our mortgage specialists.

In that review, we'll look at your current loan-to-value ratio, remaining term, and any renewal options available to you — and we'll put together a written comparison document you can keep and compare against any other options you're considering. There's no obligation to proceed with BankRetain.

This offer is specifically for existing customers at renewal — it's not something available through our standard mortgage application channel."

---

**If customer asks about rates:**

"I don't want to quote a rate before the specialist has reviewed your full mortgage account — I want to make sure the number they give you is accurate. That's exactly what the review is for. The specialist will give you a confirmed rate in writing, valid for 72 hours, during the call."

---

**Close:**

"Can I book a 30-minute slot for you with our mortgage specialist? We have availability later this week and next week. ... I'll send you a calendar confirmation to your email address. Is there anything else I can help with today?"
