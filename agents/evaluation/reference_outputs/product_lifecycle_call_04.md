---
example_id: PLC-04
churn_reason: product_lifecycle
channel: call
offer_id: PR-015
segment: private_banking
customer_signal: months_to_rate_reset=2, mortgage_balance_eur=320000
status: pass
violated_rules: []
---

# Call Script — Fixed Rate Early Lock-In (Private Banking)

**Call type:** Outbound retention — product lifecycle
**Agent context:** Private banking customer, mortgage rate expiring in 2 months.

---

**Opening (mandatory opt-out — CH-002):**

"Good afternoon, may I speak with Mr. Fontaine? ... Mr. Fontaine, good afternoon — this is Hélène calling from BankRetain's private banking team. Before anything else, I want to make sure you know you can ask us to stop contacting you at any time and I'll take care of that right away. Are you happy for me to continue for a moment? ... Wonderful.

I'm calling about your mortgage — this is a proactive call, not about any issue."

---

**Pitch:**

"Your fixed rate is due to expire in approximately two months, at the end of August 2026. I wanted to reach out now so that you have a full picture of the options available to you before the end of your current term.

As a private banking customer, you're eligible to lock in your renewal rate today — two months ahead of expiry. There's no arrangement fee, no valuation required, and the rate is guaranteed for 72 hours from when you confirm, giving you time to review the terms with your financial adviser if you'd like.

We'll also prepare a mortgage review document for you — your payment history, current equity position, and remaining term — which I can have ready before our next conversation.

I'd like to connect you with your relationship manager or our mortgage specialist at a time that suits you. When would work?"

---

**Close:**

"I'll have the review document prepared and send it to you ahead of that call. Is your preferred email address the one we have on file? ... Perfect. Thank you Mr. Fontaine — we'll speak soon."
