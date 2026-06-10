# BankRetain — Compliance Rules Reference

Synthetic compliance rules for the BankRetain AI portfolio project.
Agent 3 (Compliance Review) retrieves these rules via file search and applies them
to every outreach message draft before it is approved for dispatch.

Each rule has a `severity` field:
- **hard_block** — any violation causes the message to fail outright; no exceptions.
- **flag_for_review** — violation is noted; message is sent to the human review queue
  but is not automatically rejected.

---

## Brand Tone Rules

Rules governing language style, voice, and professionalism. Applies to all channels.

---

### BT-001 — No Urgency or Pressure Language

- **rule_id:** BT-001
- **category:** brand_tone
- **severity:** hard_block
- **rule_text:** The message must not contain language that creates artificial urgency or
  pressure to act immediately. Prohibited phrases include: "act now", "limited time only",
  "offer expires tonight", "last chance", "don't miss out", "you must respond by",
  "this offer will not be repeated". Time-limited offers may be communicated but must state
  the exact end date in neutral language (e.g. "This offer is available until 31 July 2026").

---

### BT-002 — Professional and Respectful Tone

- **rule_id:** BT-002
- **category:** brand_tone
- **severity:** hard_block
- **rule_text:** The message must maintain a professional and respectful tone throughout.
  It must not be condescending, overly casual, or use slang. The customer must be addressed
  as "you" (second person) or by first name if available — never as "dear valued customer"
  or equivalent impersonal salutations. Sarcasm, humour at the customer's expense, and
  rhetorical questions implying the customer has made a mistake are prohibited.

---

### BT-003 — No Fear-Based Messaging

- **rule_id:** BT-003
- **category:** brand_tone
- **severity:** hard_block
- **rule_text:** The message must not imply negative consequences of inaction in a way
  designed to cause anxiety or fear. Prohibited examples: "your account may be at risk",
  "you could lose your savings", "failure to act may result in account closure". It is
  permissible to state factual consequences in neutral language (e.g. "your fixed rate
  will revert to the standard variable rate on [date]").

---

### BT-004 — No Reference to Churn Prediction or Internal Scoring

- **rule_id:** BT-004
- **category:** brand_tone
- **severity:** hard_block
- **rule_text:** The message must not reference, imply, or hint at the existence of any
  internal churn model, risk score, or predictive analysis. Prohibited language includes
  any reference to the customer being "identified as at risk", "flagged for outreach",
  "selected by our system", or similar. The offer must be framed as proactive customer
  care or a routine loyalty programme — not as a response to a predicted behaviour.

---

### BT-005 — Consistent BankRetain Brand Voice

- **rule_id:** BT-005
- **category:** brand_tone
- **severity:** flag_for_review
- **rule_text:** The message should reflect BankRetain's brand voice: warm, clear,
  and straightforward. Avoid overly complex financial jargon without explanation.
  If a product term (e.g. AER, LTV, MiFID) is used, a brief plain-language explanation
  must follow in parentheses. Flag for review if the message reads as generic or could
  have been sent by any bank — it should feel personalised to the customer's situation.

---

### BT-006 — No Superlatives Without Substantiation

- **rule_id:** BT-006
- **category:** brand_tone
- **severity:** flag_for_review
- **rule_text:** Claims such as "best rate", "market-leading", "unbeatable", or "lowest
  fees" must be accompanied by a substantiated comparison (e.g. "compared to the Belgian
  market average as of Q1 2026") or must be removed. Vague superlatives without
  substantiation will be flagged for legal review before dispatch.

---

## FSMA-Style Regulatory Rules

Rules based on the Financial Services and Markets Authority (FSMA) Belgian framework
for retail financial product communication. Applied to all product offers.

---

### FSMA-001 — No Guaranteed Return Language

- **rule_id:** FSMA-001
- **category:** fsma_regulatory
- **severity:** hard_block
- **rule_text:** The message must not guarantee or imply guaranteed investment returns.
  Prohibited language: "guaranteed growth", "risk-free return", "you will earn X%",
  "your money is guaranteed to grow". For savings products with a stated fixed rate,
  the rate must be described as the rate "currently available" or "as at [date]" and
  must be qualified with: "subject to terms and conditions". Variable rate products
  must clearly state that rates may change.

---

### FSMA-002 — Mandatory Risk Disclosure for Investment Products

- **rule_id:** FSMA-002
- **category:** fsma_regulatory
- **severity:** hard_block
- **rule_text:** Any outreach message promoting an investment product (pension plans,
  discretionary portfolio management, structured products, or funds) must include the
  standard FSMA risk disclosure statement: "The value of investments can go down as
  well as up. Past performance is not a reliable indicator of future results. You may
  get back less than you invest." This statement must appear as a complete sentence,
  not paraphrased. It may appear at the end of the message or in a clearly labelled
  footnote.

---

### FSMA-003 — No Advice Without Suitability Assessment

- **rule_id:** FSMA-003
- **category:** fsma_regulatory
- **severity:** hard_block
- **rule_text:** The message must not constitute personal investment advice unless a
  MiFID II suitability assessment has been completed for this customer and the offer
  has been determined as suitable. Any offer involving an investment product must be
  framed as "information about an option available to you" — not as a recommendation
  that the customer should take action. Phrases such as "you should invest", "we recommend
  you switch", or "this is the right product for you" are prohibited for investment
  products. For non-investment products (savings accounts, current accounts, mortgages),
  a lighter disclosure applies per FSMA-005.

---

### FSMA-004 — Cooling-Off Period Must Be Referenced for New Products

- **rule_id:** FSMA-004
- **category:** fsma_regulatory
- **severity:** flag_for_review
- **rule_text:** For outreach messages that invite the customer to sign up for a new
  financial product (not a renewal or existing product modification), the message should
  reference the customer's right to a 14-day cooling-off period where applicable under
  Belgian consumer credit law. If the message promotes a product where cooling-off does
  not apply (e.g. a current account fee waiver), this rule does not apply. Flag for
  review if the product type is unclear.

---

### FSMA-005 — Fee and Charges Transparency

- **rule_id:** FSMA-005
- **category:** fsma_regulatory
- **severity:** flag_for_review
- **rule_text:** If the message references a fee, charge, or rate, the full cost
  (including any conditions) must be stated or the customer must be directed to a
  document where full cost details are available (e.g. "full terms at bankretain.be/terms").
  Partial fee disclosure — quoting a headline rate without mentioning applicable conditions —
  must be flagged for review.

---

## MiFID II–Style Product Claim Rules

Rules based on the Markets in Financial Instruments Directive (MiFID II) framework
for fair, clear, and not misleading financial product communications.

---

### MIFID-001 — No Specific Performance Claims Without Caveats

- **rule_id:** MIFID-001
- **category:** mifid_regulatory
- **severity:** hard_block
- **rule_text:** The message must not state or imply that an investment product will
  achieve a specific return or performance figure without including both a caveat and
  a reference period. For example: "our portfolios returned 7% last year — but past
  performance is not indicative of future results" is acceptable. "Our portfolios
  return 7%" or "typical return of 7%" without caveats is prohibited.

---

### MIFID-002 — Target Market Alignment

- **rule_id:** MIFID-002
- **category:** mifid_regulatory
- **severity:** hard_block
- **rule_text:** Investment or structured products must only be offered to customers
  in the defined target market for that product. For pension products: customer must
  be in working age (18–67). For discretionary portfolio management: minimum AUM
  threshold must be met and the customer must not be flagged as a vulnerable customer.
  Offering a product to a customer outside its defined target market is a hard block.

---

### MIFID-003 — Comparative Claims Must Be Accurate and Dated

- **rule_id:** MIFID-003
- **category:** mifid_regulatory
- **severity:** flag_for_review
- **rule_text:** Any comparison to market rates, competitor rates, or industry averages
  must reference the data source and the date of comparison. For example: "0.40% above
  the Belgian market average savings rate (NBB data, Q1 2026)". Undated or unsourced
  comparative claims must be flagged for compliance review before dispatch.

---

## Personalisation Requirements

Rules ensuring outreach messages are meaningfully personalised and not generic blasts.

---

### PERS-001 — Must Reference at Least One Specific Customer Signal

- **rule_id:** PERS-001
- **category:** personalisation
- **severity:** hard_block
- **rule_text:** Every outreach message must reference at least one specific, verifiable
  signal from the customer's profile. Acceptable signals include: the customer's current
  product (by name), their tenure at BankRetain, their fixed rate end date, their
  geographic region, or a recent interaction (e.g. "following our recent conversation").
  Generic messages with no personalised signal are prohibited. Referencing a churn
  signal directly (e.g. "we noticed you transferred funds to a competitor") is prohibited
  under BT-004.

---

### PERS-002 — Offer Must Match Customer Segment

- **rule_id:** PERS-002
- **category:** personalisation
- **severity:** flag_for_review
- **rule_text:** The selected offer must be appropriate for the customer's segment as
  defined in the product catalogue eligibility rules. Offering a private banking product
  to a student segment customer, or a student-only product to a private banking customer,
  must be flagged for review. Agent 2 must check segment eligibility before selecting
  an offer.

---

### PERS-003 — Channel Must Match Customer Preference

- **rule_id:** PERS-003
- **category:** personalisation
- **severity:** flag_for_review
- **rule_text:** The selected outreach channel (email or call) must match the
  `channel_fit` field of the chosen offer. If the offer is call-only and an email
  message has been drafted, flag for review. If the customer has a documented channel
  preference in their profile, that preference takes precedence over the offer default.

---

## Channel-Specific Rules

Rules that apply only to a specific outreach channel.

---

### CH-001 — Email: Unsubscribe Link Required

- **rule_id:** CH-001
- **category:** channel_specific
- **severity:** hard_block
- **rule_text:** Every outreach email must include a functioning unsubscribe link or
  a clear instruction for how to opt out of future marketing communications, in
  compliance with GDPR Article 21 and the Belgian Act of 13 June 2005 on electronic
  communications. The unsubscribe mechanism must be no more than one click for email.
  The link text must be clearly labelled (e.g. "Unsubscribe" or "Manage your
  communication preferences") — it must not be hidden in small print or footer boilerplate
  that is easily overlooked.

---

### CH-002 — Call Script: Verbal Opt-Out Required

- **rule_id:** CH-002
- **category:** channel_specific
- **severity:** hard_block
- **rule_text:** Every call script must include a mandatory verbal opt-out offer at the
  start of the conversation: "Before I continue, I want to let you know that you can
  ask us at any time to stop contacting you about offers — just let me know and I'll
  update your preferences immediately." The agent drafting a call script must include
  this opening statement verbatim or with equivalent content. Omitting this statement
  is a hard block.

---

### CH-003 — Call Script: Must Not Simulate a Service Call

- **rule_id:** CH-003
- **category:** channel_specific
- **severity:** hard_block
- **rule_text:** A call script drafted as a retention outreach must clearly identify
  itself as a marketing/loyalty call within the first 30 seconds. It must not open
  with language that implies the call is about a security alert, account issue, or
  service notification if the primary purpose is a product offer. Misleading call
  openings that exploit urgency or concern to gain engagement are prohibited.

---

### CH-004 — Email: Subject Line Must Not Be Misleading

- **rule_id:** CH-004
- **category:** channel_specific
- **severity:** flag_for_review
- **rule_text:** The email subject line must accurately reflect the content of the
  email. Subject lines that imply an account alert, security notification, or required
  action when the email is a promotional offer must be flagged for review. Examples of
  prohibited subject lines: "Action required on your account", "Important update about
  your account". Acceptable examples: "A loyalty offer from BankRetain",
  "Your fixed rate renewal — options available to you".
