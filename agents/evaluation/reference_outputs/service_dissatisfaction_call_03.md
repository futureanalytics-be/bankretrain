---
example_id: SDC-03
churn_reason: service_dissatisfaction
channel: call
offer_id: PR-011
segment: standard
customer_signal: complaints_open=1, oldest_complaint_days=22, complaint_category=fee_dispute
status: pass
violated_rules: []
---

# Call Script — Complaint Fast-Track + Goodwill Credit

**Call type:** Outbound retention — complaint resolution
**Agent context:** Open fee dispute complaint, 22 days old. Goodwill credit to be offered on resolution.

---

**Opening (mandatory opt-out — CH-002):**

"Hello, is that Mr. Nijs? ... Good afternoon Mr. Nijs, this is Elien calling from BankRetain's customer resolution team. Before I go on, I want to make sure you know you can ask us to stop contacting you at any point — just let me know. May I continue? ... Thank you.

I'm calling specifically about the query you raised with us recently regarding your account fees — I want to make sure we resolve this for you properly."

---

**Pitch:**

"I can see your query has been open for just over three weeks, and that's longer than it should have been. I want to apologise for that, and I'm calling to make sure it gets resolved this week.

I've escalated your case to our senior resolution team. You'll receive a direct call from them within two business days — their target is to close your case within five business days of today.

Once your case is resolved, we'd like to apply a €25 goodwill credit to your account as an acknowledgement of the time this has taken. That will appear within five business days of resolution.

Is there any additional context about your fee query that you'd like me to add to the case notes right now? I want to make sure the team has everything they need."

---

**Close:**

"Thank you — I've updated the notes. You'll hear from the resolution team by Wednesday at the latest. Is there anything else I can help with today? ... And please feel free to contact us directly on +32 2 123 45 67 if you'd like an update in the meantime."
