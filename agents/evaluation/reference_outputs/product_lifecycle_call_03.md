---
example_id: PLC-03
churn_reason: product_lifecycle
channel: call
offer_id: PR-020
segment: standard
customer_signal: salary_account_flag=false, avg_monthly_inflow_eur=2800, tenure_months=14
status: pass
violated_rules: []
---

# Call Script — Salary Domiciliation Switch Bonus

**Call type:** Outbound retention — product lifecycle
**Agent context:** Customer receives consistent inflow but salary is not domiciled at BankRetain.

---

**Opening (mandatory opt-out — CH-002):**

"Hello, may I speak with Ms. Wouters? ... Hi Ms. Wouters, this is Bram calling from BankRetain. Just before I start — you can ask us at any time to stop contacting you about offers, and I'll sort that immediately. Is now an okay time? ... Great, thank you.

I'm making a loyalty call today."

---

**Pitch:**

"I wanted to share an option that a lot of our customers find useful — and that comes with a one-time bonus right now.

If you move your salary payment to your BankRetain current account, you'll receive a €100 bonus credited within 30 days of your first qualifying salary landing. You'd also unlock a preferential savings rate — an extra 0.20% AER on your existing savings balance — and your card fees would be waived for 12 months.

The switch itself is simple: you just notify your employer with your BankRetain IBAN. We can provide a pre-filled employer notification letter to make that even easier — it takes about two minutes on our end.

The total benefit — the €100 bonus plus 12 months of waived card fees — is worth up to €196 depending on your current fee arrangement."

---

**If customer says 'I need to think about it':**

"Absolutely — no rush. Would it help if I sent you the details by email so you have everything in writing? The offer is open until 31 October 2026."

---

**Close:**

"I'll send that over now. Is there anything else I can help with? ... And if you'd prefer not to receive loyalty calls in future, just say the word."
