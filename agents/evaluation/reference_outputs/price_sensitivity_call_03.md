---
example_id: PSC-03
churn_reason: price_sensitivity
channel: call
offer_id: PR-008
segment: standard
customer_signal: overdraft_use=3_times_last_6m, competitor_transfer_count=2
status: pass
violated_rules: []
---

# Call Script — Overdraft Interest Waiver

**Call type:** Outbound retention — product benefit
**Agent context:** Customer has used the overdraft facility three times in the last six months and has made competitor transfers.

---

**Opening (mandatory opt-out — CH-002):**

"Hello, may I speak with Mr. Claes? ... Hi Mr. Claes, this is Fien calling from BankRetain. I'm making a loyalty call today — not about any issue with your account. I just want to make sure you know that at any time you can ask me to stop contacting you about offers, and I'll take care of that right away. Fine if I continue for a moment? ... Great, thank you.

---

**Pitch:**

"I'm calling because we'd like to offer you something in recognition of how you manage your BankRetain account.

We have a three-month overdraft interest waiver available to you — meaning any interest charges on your existing overdraft facility would be suspended for three months, starting from next month. Your overdraft limit stays exactly as it is; the only change is that the interest charges won't apply during that period.

After three months, your standard overdraft interest rate resumes as normal. We'll send you a written reminder 14 days before that happens.

There's no form to complete and no application — if you'd like to take this up, I can activate it for you right now on this call."

---

**If customer asks 'why are you offering this?':**

"It's part of our standard loyalty programme for customers who use their account actively and responsibly. We review accounts periodically and extend offers where we think they'll be useful."

---

**Close:**

"Shall I go ahead and activate the waiver now? ... Done — you'll receive a confirmation SMS shortly. Is there anything else I can help you with today? ... And as always, if you'd prefer we don't call with offers in future, just let me know."
