---
example_id: SDC-02
churn_reason: service_dissatisfaction
channel: call
offer_id: PR-010
segment: private_banking
customer_signal: nps_score_last=3, avg_monthly_inflow_eur=4200, complaints_open=1
status: pass
violated_rules: []
---

# Call Script — Dedicated Relationship Manager Assignment

**Call type:** Outbound retention — service uplift
**Agent context:** Private banking customer, NPS 3, €4,200 monthly inflow, 1 open complaint.

---

**Opening (mandatory opt-out — CH-002):**

"Good morning, may I speak with Ms. Hermans? ... Good morning Ms. Hermans, this is Philippe calling from BankRetain's private banking team. Before I go further — at any point during or after this call you can ask us to stop contacting you with offers, and we'll do that straight away. Is it okay if I continue? ... Thank you.

I'm making a loyalty call today — this is not about any outstanding matter on your account, though I'll address that if you'd like."

---

**Pitch:**

"I'm calling because I'd like to offer you something that I think will make your day-to-day banking experience with us noticeably better.

We'd like to assign you a dedicated relationship manager — a named individual at BankRetain who will be your single point of contact for any account query, product question, or service issue. That means no queuing, no being transferred between departments.

Your relationship manager would also reach out proactively with quarterly account reviews and any rate alerts that might be relevant to your situation. The service is available to you at no additional cost.

I'd also like to make sure your open query is prioritised — would you like me to escalate that to your new relationship manager as a first task?"

---

**Close:**

"I'll arrange for your relationship manager to call you within two business days to introduce themselves and get your preferences on file. You'll receive a confirmation email with their direct contact details within the hour. Is there anything else I can help with today? ... And if you'd prefer to opt out of future loyalty calls, just let me know."
