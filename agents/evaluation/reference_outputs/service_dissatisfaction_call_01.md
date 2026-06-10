---
example_id: SDC-01
churn_reason: service_dissatisfaction
channel: call
offer_id: PR-009
segment: standard
customer_signal: complaints_open=2, nps_score_last=4, tenure_months=18
status: pass
violated_rules: []
---

# Call Script — Priority Service Upgrade

**Call type:** Outbound retention — service escalation
**Agent context:** Customer has 2 open complaints and NPS of 4. Complaint status must be acknowledged empathetically.

---

**Opening (mandatory opt-out — CH-002):**

"Good afternoon, may I speak with Mr. Bogaert? ... Hello Mr. Bogaert, this is Sara calling from BankRetain's customer care team. Before I continue, I want to let you know that you can ask us at any time to stop contacting you — just let me know and I'll update your preferences immediately. Would it be okay to continue for a moment? ... Thank you.

I'm calling today as a loyalty call — not about the specific queries you have open with us, though I do want to make sure those are being handled properly."

---

**Pitch:**

"I can see from your account that you've had to contact us more than once recently, and I want to make sure that changes.

I'd like to enrol you in our Priority Service programme — at no cost to you. This means a dedicated phone queue with an average wait time of under two minutes, a guaranteed callback within four hours if our lines are busy, and a named contact at BankRetain for the first three months.

Your two open queries will also be escalated to our senior resolution team today, with a target to have both closed by the end of this week. You'll receive an update by SMS by close of business tomorrow.

Would that work for you?"

---

**If customer expresses frustration:**

"I completely understand, and I'm sorry we haven't resolved this sooner. I'm going to make a personal note on your account right now and make sure the senior team picks this up today — not tomorrow, today. Can I get your permission to have someone call you back within four hours?"

---

**Close:**

"I've enrolled you in Priority Service. You'll receive a confirmation email with your named contact shortly. Is there anything else I can help you with right now? ... And if you'd prefer we don't contact you for offers in future, please say — I'll note that immediately."
