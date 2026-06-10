# BankRetain — Retention Product Catalogue

Synthetic Belgian retail banking retention offers for the BankRetain AI portfolio project.
Each offer is designed to address a specific churn signal and is referenced by Agent 2
(Offer Selection) when drafting personalised retention outreach.

All amounts in EUR. Eligibility rules are evaluated at the time of outreach generation.

---

## Price Sensitivity Offers

Customers showing: competitor transfer activity, NPS < 6, fee complaints, inbound salary
stop, or explicit cost-related verbatim feedback.

---

### PR-001 — Zero-Fee Loyalty Package

- **product_type:** fee_waiver
- **target_segment:** standard, starter
- **retention_use_case:** price_sensitivity
- **channel_fit:** email, call
- **eligibility_rules:**
  - Customer tenure ≥ 12 months
  - At least 1 competitor transfer in the last 90 days OR NPS score ≤ 5
  - No existing fee-waiver offer active
- **offer_description:** Waive all monthly account maintenance fees for 12 months
  (standard: €8/month, starter: €4/month). Communicated as a loyalty reward, not a
  reaction to churn signals. Offer letter includes a dedicated callback number.
- **offer_value:** Up to €96 saving over 12 months (standard tier)

---

### PR-002 — Savings Bonus Rate Boost

- **product_type:** bonus_rate
- **target_segment:** standard, private_banking
- **retention_use_case:** price_sensitivity
- **channel_fit:** email, call
- **eligibility_rules:**
  - Customer holds an active savings account
  - Balance ≥ €5,000
  - Competitor transfer in the last 90 days OR days_since_last_login > 60
- **offer_description:** +0.40% AER on existing savings balance for 6 months, applied
  automatically — no product switch required. Rate reverts to standard at end of period
  with 30-day advance notice.
- **offer_value:** €200 additional interest on €50,000 balance over 6 months

---

### PR-003 — Cashback on Daily Spending

- **product_type:** cashback
- **target_segment:** standard, student
- **retention_use_case:** price_sensitivity
- **channel_fit:** email
- **eligibility_rules:**
  - Customer uses debit card at least 5 times per month
  - No cashback programme currently active
  - Age ≤ 45 (student and young professional focus)
- **offer_description:** 1.5% cashback on all contactless and online card transactions,
  capped at €15/month, for 6 months. Cashback credited monthly to current account.
  Requires continued primary card usage.
- **offer_value:** Up to €90 over 6 months

---

### PR-004 — Mortgage Rate Discount — Loyalty Pricing

- **product_type:** rate_discount
- **target_segment:** standard, private_banking
- **retention_use_case:** price_sensitivity
- **channel_fit:** call
- **eligibility_rules:**
  - Customer holds an active mortgage with fixed_rate_end_date within 6 months
  - Competitor transfer in last 90 days
  - No active rate renegotiation in progress
- **offer_description:** Offer a loyalty pricing review: up to -0.15% reduction on the
  renewal fixed rate, conditional on keeping salary domiciliation at BankRetain for
  the new fixed-rate term. Presented as proactive loyalty pricing, not a counter-offer.
- **offer_value:** ~€750 saving over a 5-year term on a €200,000 mortgage

---

### PR-005 — Annual Fee Refund — Long-Tenure Customers

- **product_type:** fee_refund
- **target_segment:** private_banking
- **retention_use_case:** price_sensitivity
- **channel_fit:** call
- **eligibility_rules:**
  - Customer tenure ≥ 5 years
  - product_count ≥ 3
  - NPS score ≤ 6 in last response
- **offer_description:** One-time refund of the most recent annual card or account fee
  as a "tenure appreciation" gesture. Relationship manager call required to deliver this
  offer — not automated. Refund processed within 5 business days.
- **offer_value:** Up to €150 one-time refund

---

### PR-006 — Bundle Discount — Current Account + Savings + Insurance

- **product_type:** bundle_discount
- **target_segment:** standard, private_banking
- **retention_use_case:** price_sensitivity
- **channel_fit:** email, call
- **eligibility_rules:**
  - Customer holds current account and at least one other active product
  - Monthly fee currently charged
  - Competitor transfer in last 90 days
- **offer_description:** Switch to the BankRetain Plus bundle: current account + savings
  + travel insurance for a combined monthly fee of €9.90 (saving up to €6/month vs
  individual products). 3-month free trial period before billing begins.
- **offer_value:** Up to €72 saving per year after trial

---

### PR-007 — Refer-a-Friend Bonus (Price-Sensitive Anchor)

- **product_type:** referral_bonus
- **target_segment:** standard, student
- **retention_use_case:** price_sensitivity
- **channel_fit:** email
- **eligibility_rules:**
  - Customer has been active in the app in the last 30 days
  - No pending churn flag older than 90 days
  - Not already enrolled in a referral programme
- **offer_description:** €50 for the customer and €50 for each referred friend who opens
  an account and makes 3 transactions within 60 days. Maximum 3 referrals per customer.
  Bonus credited within 30 days of qualifying transaction.
- **offer_value:** Up to €150 if 3 referrals qualify

---

### PR-008 — Overdraft Interest Waiver

- **product_type:** interest_waiver
- **target_segment:** standard, starter, student
- **retention_use_case:** price_sensitivity
- **channel_fit:** email, call
- **eligibility_rules:**
  - Customer has used overdraft at least twice in the last 6 months
  - complaints_open = 0 (avoid offer during active complaint)
  - Competitor transfer in last 90 days
- **offer_description:** Waive overdraft interest charges for 3 months. Customer retains
  existing overdraft limit. After 3 months, standard interest rate resumes. Presented
  as recognition of responsible account management.
- **offer_value:** Typically €30–€90 depending on usage pattern

---

## Service Dissatisfaction Offers

Customers showing: open complaints, low NPS, long resolution times, app inactivity
following a service incident.

---

### PR-009 — Priority Service Lane

- **product_type:** priority_service
- **target_segment:** standard, private_banking
- **retention_use_case:** service_dissatisfaction
- **channel_fit:** call
- **eligibility_rules:**
  - complaints_open ≥ 1 OR NPS score ≤ 5
  - Customer tenure ≥ 6 months
  - Not already on priority tier
- **offer_description:** Upgrade to BankRetain Priority: dedicated phone queue (avg wait
  < 2 min), callback guarantee within 4 hours, named contact for first 3 months. No
  additional cost. Delivered via relationship manager call — not automated email.
- **offer_value:** Service uplift; no direct monetary value

---

### PR-010 — Dedicated Relationship Manager Assignment

- **product_type:** relationship_manager
- **target_segment:** private_banking, standard (high-value)
- **retention_use_case:** service_dissatisfaction
- **channel_fit:** call
- **eligibility_rules:**
  - NPS score ≤ 4 OR complaints_open ≥ 2
  - avg_monthly_inflow_eur ≥ 3,000
  - No relationship manager currently assigned
- **offer_description:** Assign a named relationship manager for 12 months. Includes
  quarterly review calls, proactive rate alerts, and a direct mobile number. Positioned
  as an exclusive service tier, not a complaint response.
- **offer_value:** Service uplift; estimated retention value €500+/year

---

### PR-011 — Complaint Resolution Fast-Track + Goodwill Credit

- **product_type:** goodwill_credit
- **target_segment:** standard, starter, student
- **retention_use_case:** service_dissatisfaction
- **channel_fit:** call
- **eligibility_rules:**
  - complaints_open ≥ 1
  - Oldest open complaint > 14 days
  - Not already issued a goodwill credit in last 12 months
- **offer_description:** Fast-track open complaint to senior resolution team (target
  closure within 5 business days). On resolution, apply a €25 goodwill credit to the
  account. Call script must reference the specific complaint category.
- **offer_value:** €25 credit + faster resolution

---

### PR-012 — App Usability Session + Digital Onboarding

- **product_type:** onboarding_session
- **target_segment:** standard, starter
- **retention_use_case:** service_dissatisfaction
- **channel_fit:** email, call
- **eligibility_rules:**
  - days_since_last_login > 45
  - app_logins_last_90d < 3
  - Customer tenure < 24 months
- **offer_description:** Invite to a 20-minute video session with a digital banking
  specialist. Covers: setting up notifications, card controls, savings pots, and
  payment scheduling. Followed by a 30-day email tips series. Entirely optional.
- **offer_value:** Service uplift; targets digitally disengaged customers

---

### PR-013 — Service Guarantee Pledge

- **product_type:** service_guarantee
- **target_segment:** private_banking, standard
- **retention_use_case:** service_dissatisfaction
- **channel_fit:** call
- **eligibility_rules:**
  - NPS score ≤ 5
  - Customer tenure ≥ 12 months
  - No active complaint (complaint must be resolved first — use PR-011 first)
- **offer_description:** Enrol in BankRetain's Service Guarantee: if any future complaint
  is not resolved within 10 business days, an automatic €30 credit is applied, no
  questions asked. Delivered as a written commitment from the branch or RM.
- **offer_value:** €30 conditional credit + trust restoration signal

---

### PR-014 — Fee Compensation for Service Failure

- **product_type:** fee_compensation
- **target_segment:** standard, starter, student
- **retention_use_case:** service_dissatisfaction
- **channel_fit:** call
- **eligibility_rules:**
  - complaints_open ≥ 1 AND complaint category is service-related (not product)
  - Monthly fee charged in month of complaint
- **offer_description:** Refund one month's account fees as a service failure
  acknowledgement. Delivered during complaint resolution call — not as a standalone
  outreach. Must be paired with a concrete resolution commitment.
- **offer_value:** €4–€15 depending on account tier

---

## Product Lifecycle Offers

Customers showing: fixed rate end within 6 months, product reduction signals,
high competitor transfer count to mortgage/savings providers.

---

### PR-015 — Fixed Rate Renewal — Early Lock-In

- **product_type:** rate_lock
- **target_segment:** standard, private_banking
- **retention_use_case:** product_lifecycle
- **channel_fit:** call, email
- **eligibility_rules:**
  - Active mortgage with fixed_rate_end_date within 1–6 months
  - No active renewal discussion in last 30 days
- **offer_description:** Lock in today's fixed rate 3 months before the current term
  ends — no arrangement fee, no valuation required for like-for-like renewal. Rate
  guaranteed for 72 hours from call. Includes a free mortgage review document
  summarising payment history and equity position.
- **offer_value:** Rate certainty; avoids competitor shopping window

---

### PR-016 — Mortgage Refinance Review

- **product_type:** refinance_review
- **target_segment:** standard, private_banking
- **retention_use_case:** product_lifecycle
- **channel_fit:** call
- **eligibility_rules:**
  - Active mortgage with fixed_rate_end_date within 3 months OR variable rate
  - Competitor transfer in last 90 days
  - Mortgage balance ≥ €75,000
- **offer_description:** No-obligation 30-minute refinancing review with a mortgage
  specialist. Reviews current LTV, remaining term, and compares BankRetain's renewal
  options against published market rates. Customer receives a written comparison document.
- **offer_value:** Potential multi-year interest saving; strong retention signal if booked

---

### PR-017 — Investment Product Upgrade — Private Banking Transition

- **product_type:** product_upgrade
- **target_segment:** standard (high-value)
- **retention_use_case:** product_lifecycle
- **channel_fit:** call
- **eligibility_rules:**
  - avg_monthly_inflow_eur ≥ 5,000
  - product_count ≤ 2
  - Customer tenure ≥ 24 months
  - No existing investment products
- **offer_description:** Invitation to explore BankRetain's discretionary portfolio
  management service (min. €25,000 AUM). Includes a complimentary financial planning
  session. No obligation. Positioned as recognition of the customer's financial growth.
- **offer_value:** Upsell + retention; average AUM retention value €1,200/year

---

### PR-018 — Product Consolidation Package

- **product_type:** consolidation
- **target_segment:** standard, private_banking
- **retention_use_case:** product_lifecycle
- **channel_fit:** email, call
- **eligibility_rules:**
  - product_count ≥ 3 across multiple providers (inferred from competitor transfers)
  - salary_account_flag = false
- **offer_description:** Consolidate current account, savings, and insurance with
  BankRetain. Customer receives a personalised consolidation report showing the
  combined fee saving and a single monthly statement. Salary domiciliation bonus:
  €75 one-time credit if salary is moved within 60 days.
- **offer_value:** €75 salary credit + ongoing fee saving

---

### PR-019 — Pension Savings Starter

- **product_type:** pension_starter
- **target_segment:** standard
- **retention_use_case:** product_lifecycle
- **channel_fit:** email
- **eligibility_rules:**
  - Age 30–55 (inferred from segment and tenure proxy)
  - No existing pension or long-term savings product
  - product_count ≤ 2
- **offer_description:** Open a tax-advantaged pension savings plan (Belgian pillar 3)
  with no minimum contribution for the first 6 months. BankRetain matches the first
  €100 contribution. Fully digital onboarding, no branch visit required.
- **offer_value:** €100 match + long-term AUM retention

---

### PR-020 — Salary Domiciliation Switch Bonus

- **product_type:** salary_switch_bonus
- **target_segment:** standard, starter
- **retention_use_case:** product_lifecycle
- **channel_fit:** email, call
- **eligibility_rules:**
  - salary_account_flag = false
  - avg_monthly_inflow_eur ≥ 1,500
  - Customer tenure ≥ 3 months
- **offer_description:** Move salary domiciliation to BankRetain and receive a one-time
  €100 bonus credited within 30 days of first qualifying salary credit. Unlocks access
  to preferential savings rate (+0.20% AER) and waived card fees for 12 months.
- **offer_value:** €100 bonus + up to €96 fee saving

---

## Inactivity Offers

Customers showing: high days_since_last_login, low app sessions, no transactions in 60+
days, product count declining.

---

### PR-021 — Re-Engagement Cashback Sprint

- **product_type:** reengagement_cashback
- **target_segment:** standard, starter, student
- **retention_use_case:** inactivity
- **channel_fit:** email
- **eligibility_rules:**
  - days_since_last_login > 60
  - app_logins_last_90d < 5
  - No cashback programme active
- **offer_description:** Complete 5 card transactions in the next 30 days and receive
  €20 cashback. Tracked automatically via the app. Designed to rebuild the habit of
  using BankRetain as primary transactional account. Push notification reminder at
  day 15 if target not yet reached.
- **offer_value:** €20 cashback + habit reformation

---

### PR-022 — Digital Feature Discovery Reward

- **product_type:** feature_discovery
- **target_segment:** standard, student, starter
- **retention_use_case:** inactivity
- **channel_fit:** email
- **eligibility_rules:**
  - days_since_last_login > 30
  - app_logins_last_30d < 2
  - Customer tenure ≥ 6 months
- **offer_description:** Guided in-app journey: unlock 3 unused features (e.g. savings
  pots, spending insights, card freeze) and earn a €10 reward. Journey completion
  tracked in-app. Reward credited automatically on completion.
- **offer_value:** €10 reward + digital engagement uplift

---

### PR-023 — Dormant Account Re-Activation Offer

- **product_type:** reactivation_offer
- **target_segment:** standard, starter
- **retention_use_case:** inactivity
- **channel_fit:** email, call
- **eligibility_rules:**
  - days_since_last_login > 90
  - Last transaction > 60 days ago
  - Account balance > €0 (account not empty)
- **offer_description:** "We've saved your spot" reactivation campaign. Customer receives
  a personalised email with their account summary and a €15 credit if they log in and
  make one transaction within 14 days. Call follow-up on day 7 if email unopened.
- **offer_value:** €15 reactivation credit

---

### PR-024 — Savings Goal Setup Incentive

- **product_type:** savings_goal_incentive
- **target_segment:** standard, student, starter
- **retention_use_case:** inactivity
- **channel_fit:** email
- **eligibility_rules:**
  - No active savings goal set in the app
  - app_logins_last_90d < 10
  - Has a savings account (active product)
- **offer_description:** Set up a savings goal in the BankRetain app (holiday, home
  deposit, emergency fund, etc.) and receive a €0.25% bonus rate on the first €2,000
  saved toward the goal for 3 months. Goal must be ≥ €500 target value to qualify.
- **offer_value:** Up to €15 bonus interest + engagement uplift

---

### PR-025 — Loyalty Milestone Reward

- **product_type:** loyalty_milestone
- **target_segment:** standard, private_banking
- **retention_use_case:** inactivity
- **channel_fit:** email
- **eligibility_rules:**
  - Customer tenure crosses a milestone: 1 year, 3 years, 5 years, or 10 years
  - days_since_last_login > 30
  - No loyalty milestone reward issued in last 12 months
- **offer_description:** Personalised anniversary message with a milestone reward scaled
  to tenure: 1 year → €10 credit, 3 years → €25 credit, 5 years → €50 credit,
  10 years → €100 credit + private banking review invitation. Delivered by email with
  a card design referencing the customer's tenure year.
- **offer_value:** €10–€100 depending on tenure milestone
