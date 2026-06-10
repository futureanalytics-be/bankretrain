---
example_id: IC-02
churn_reason: inactivity
channel: call
offer_id: PR-023
segment: standard
customer_signal: days_since_last_login=92, last_transaction_days_ago=65
status: pass
violated_rules: []
---

# Call Script — Dormant Account Re-Activation (Call Follow-Up)

**Call type:** Outbound retention — re-activation follow-up (email was sent 7 days ago, no response)
**Agent context:** Customer inactive 90+ days. Email sent previously with €15 re-activation offer; no login recorded.

---

**Opening (mandatory opt-out — CH-002):**

"Good morning, may I speak with Ms. Bogaerts? ... Hello Ms. Bogaerts, this is Jonas calling from BankRetain. Before I continue — you can ask us at any time to stop these calls and I'll update your preferences right away. Is it okay if I continue? ... Thank you.

I'm making a loyalty call today."

---

**Pitch:**

"We sent you an email recently about your BankRetain account — I'm following up to make sure you received it and to answer any questions.

Your account is completely in order, and your balance is safe. We simply wanted to reach out because we haven't seen you in the app or online banking for a little while, and we want to make sure everything is working as it should.

We have a €15 welcome-back credit available to you — it applies automatically if you log in and make one transaction by 24 June 2026. It could be any card payment, a transfer, anything.

If you've had any trouble logging in — perhaps a forgotten password or a new phone — I can help you get back in right now, or transfer you to our digital support team."

---

**If customer says they've been meaning to switch banks:**

"I appreciate you being straight with me. Could I ask what's prompted that? I'd like to make sure we've given you every opportunity to raise anything that wasn't working — and if there's something specific, I'd like to address it."

---

**Close:**

"The €15 offer is available until 24 June 2026. Is there anything I can help you with today? ... And if you'd prefer we don't follow up again, just let me know — I'll note that now."
