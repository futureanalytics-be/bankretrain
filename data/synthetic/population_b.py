"""
population_b.py — BankRetain Population B generator (autumn/winter drift)

Generates 50,000 synthetic Belgian retail banking customers representing
the autumn/winter behavioural period. Used to simulate production drift
and trigger retraining of churn model v2.

Population B characteristics vs Population A:
  - Mortgage rate resets spike: Belgian fixed-rate mortgages cluster
    renewals in September. months_to_rate_reset < 3 is much more common.
  - Higher competitor transfer frequency: customers shopping around
    at rate reset time. ~18–22% show this signal.
  - App login decline: seasonal disengagement, colder months.
  - ~14% churn rate after label computation (vs ~10% in Population A).

This deliberate drift is what causes model v1 (trained on Population A)
to lose precision when scoring Population B — triggering the drift monitor
and the automated retraining pipeline.
"""

import numpy as np
import pandas as pd
from datetime import date, timedelta
from typing import Dict

from population_a import (
    COMPETITOR_BICS,
    REGIONS,
    REGION_WEIGHTS,
    SEGMENTS,
    SEGMENT_WEIGHTS,
    PRODUCT_TYPES,
    _generate_products,
    _product_row,
    _fake_iban,
    _generate_branch_visits,
)

# Population B snapshot: autumn
SNAPSHOT_DATE    = date(2025, 10, 1)
FORWARD_END_DATE = date(2025, 11, 30)   # 60 days after snapshot


def generate_population_b(n_customers: int = 50_000, random_seed: int = 99) -> Dict[str, pd.DataFrame]:
    """
    Generate Population B synthetic data.

    Returns a dict of DataFrames matching the Azure SQL schema.
    Schema is identical to Population A — only the distributions differ.
    Target churn rate: ~14% (higher than Population A due to seasonal drift).
    """
    rng = np.random.default_rng(random_seed)

    customers = _generate_customers_b(n_customers, rng)

    # Pre-assign 14% churners so label_generator produces the expected rate
    churn_idx    = rng.choice(n_customers, size=int(n_customers * 0.14), replace=False)
    churning_ids = set(customers.iloc[churn_idx]["customer_id"])

    products       = _generate_products()
    customer_prods = _generate_customer_products_b(customers, products, rng, churning_ids)
    transactions   = _generate_transactions_b(customers, customer_prods, rng, churning_ids)
    complaints     = _generate_complaints_b(customers, rng)
    nps            = _generate_nps_responses_b(customers, rng)
    app_sessions   = _generate_app_sessions_b(customers, rng, churning_ids)
    branch_visits  = _generate_branch_visits(customers, rng)

    return {
        "customers":         customers,
        "products":          products,
        "customer_products": customer_prods,
        "transactions":      transactions,
        "complaints":        complaints,
        "nps_responses":     nps,
        "app_sessions":      app_sessions,
        "branch_visits":     branch_visits,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Table generators — Population B overrides
# ─────────────────────────────────────────────────────────────────────────────

def _generate_customers_b(n: int, rng: np.random.Generator) -> pd.DataFrame:
    """Customer master for Population B — same schema, autumn snapshot date."""
    customer_ids = [f"C{i:06d}" for i in range(1, n + 1)]
    ages         = rng.integers(18, 75, size=n)
    regions      = rng.choice(REGIONS,  size=n, p=REGION_WEIGHTS)
    segments     = rng.choice(SEGMENTS, size=n, p=SEGMENT_WEIGHTS)
    tenure_days  = rng.integers(30, 25 * 365, size=n)

    customer_since = [
        SNAPSHOT_DATE - timedelta(days=int(d)) for d in tenure_days
    ]

    preferred_language = []
    for region in regions:
        if region == "Flanders":
            preferred_language.append(rng.choice(["nl", "en"], p=[0.90, 0.10]))
        elif region == "Wallonia":
            preferred_language.append(rng.choice(["fr", "en"], p=[0.88, 0.12]))
        else:
            preferred_language.append(rng.choice(["nl", "fr", "en"], p=[0.40, 0.45, 0.15]))

    salary_flags = []
    for seg in segments:
        if seg in ("standard", "private_banking"):
            salary_flags.append(bool(rng.choice([True, False], p=[0.82, 0.18])))
        elif seg == "starter":
            salary_flags.append(bool(rng.choice([True, False], p=[0.65, 0.35])))
        else:
            salary_flags.append(bool(rng.choice([True, False], p=[0.30, 0.70])))

    rm_ids = [
        f"RM{rng.integers(1, 20):03d}" if seg == "private_banking" else None
        for seg in segments
    ]

    return pd.DataFrame({
        "customer_id":             customer_ids,
        "snapshot_date":           SNAPSHOT_DATE,
        "age":                     ages,
        "region":                  regions,
        "segment":                 segments,
        "customer_since_date":     customer_since,
        "preferred_language":      preferred_language,
        "salary_account_flag":     salary_flags,
        "relationship_manager_id": rm_ids,
    })


def _generate_customer_products_b(
    customers: pd.DataFrame,
    products: pd.DataFrame,
    rng: np.random.Generator,
    churning_ids: set = None,
) -> pd.DataFrame:
    """
    Customer-product holdings for Population B.

    KEY DIFFERENCE vs Population A:
    Mortgage fixed rate end dates cluster around autumn 2025 — reflecting
    the Belgian September renewal concentration. This is the primary
    drift signal the model monitor will detect.
    """
    rows = []
    product_map = dict(zip(products["product_type"], products["product_id"]))

    for _, cust in customers.iterrows():
        cid  = cust["customer_id"]
        seg  = cust["segment"]
        since = cust["customer_since_date"]

        # Current account — always
        rows.append(_product_row(cid, product_map["current_account"], since, rng, status="active"))

        # Savings
        if rng.random() < 0.70:
            rows.append(_product_row(cid, product_map["savings_account"], since, rng))

        # Mortgage — Population B: resets concentrated in next 0–4 months
        if seg in ("standard", "private_banking") and rng.random() < 0.35:
            # 60% of mortgages resetting within 4 months (September clustering)
            if rng.random() < 0.60:
                months_to_reset = int(rng.integers(0, 4))
            else:
                months_to_reset = int(rng.integers(4, 120))
            fixed_end = SNAPSHOT_DATE + timedelta(days=months_to_reset * 30)
            rows.append(_product_row(
                cid, product_map["mortgage"], since, rng,
                fixed_rate_end_date=fixed_end,
            ))

        # Consumer credit
        if seg != "student" and rng.random() < 0.25:
            rows.append(_product_row(cid, product_map["consumer_credit"], since, rng))

        # Investment
        invest_prob = 0.40 if seg == "private_banking" else 0.10
        if rng.random() < invest_prob:
            rows.append(_product_row(cid, product_map["investment"], since, rng))

        # Insurance
        has_mortgage = any(
            r["product_id"] == product_map["mortgage"] for r in rows if r["customer_id"] == cid
        )
        if has_mortgage and rng.random() < 0.35:
            rows.append(_product_row(cid, product_map["insurance"], since, rng))

        # Churners: close one non-current-account product in the forward window (signal 3)
        if churning_ids and cid in churning_ids and rng.random() < 0.50:
            cust_rows = [r for r in rows if r["customer_id"] == cid and r["product_id"] != product_map["current_account"]]
            if cust_rows:
                target = cust_rows[rng.integers(0, len(cust_rows))]
                target["end_date"] = SNAPSHOT_DATE + timedelta(days=int(rng.integers(5, 55)))
                target["status"]   = "closed"

    return pd.DataFrame(rows)


def _generate_transactions_b(
    customers: pd.DataFrame,
    customer_products: pd.DataFrame,
    rng: np.random.Generator,
    churning_ids: set = None,
) -> pd.DataFrame:
    """
    Transactions for Population B.

    KEY DIFFERENCE vs Population A:
    Higher competitor transfer frequency — customers shopping around
    during mortgage rate reset season. ~20% show 2–5 competitor transfers.
    """
    rows = []
    hist_start      = SNAPSHOT_DATE - timedelta(days=90)
    competitor_bics = list(COMPETITOR_BICS.values())
    tx_id = 1

    for _, cust in customers.iterrows():
        cid        = cust["customer_id"]
        sal        = cust["salary_account_flag"]
        is_churner = churning_ids and cid in churning_ids

        # ── Historical window (pre-snapshot, 90 days) ──────────────────────
        n_tx = int(rng.integers(40, 130))
        for _ in range(n_tx):
            tx_date   = hist_start + timedelta(days=int(rng.integers(0, 90)))
            direction = rng.choice(["credit", "debit"], p=[0.35, 0.65])
            amount    = round(float(min(rng.lognormal(mean=4.5, sigma=1.2), 25_000.0)), 2)
            category  = rng.choice([
                "salary", "rent", "utilities", "groceries",
                "restaurants", "transport", "online_retail",
                "atm_withdrawal", "transfer", "insurance",
            ], p=[0.08, 0.05, 0.06, 0.12, 0.10, 0.08, 0.15, 0.10, 0.18, 0.08])

            if category == "salary" and direction == "credit" and sal:
                amount = round(float(rng.uniform(2_200, 6_500)), 2)

            is_competitor, counterparty_bic, counterparty_iban = False, None, None
            if category == "transfer" and direction == "debit" and rng.random() < 0.20:
                counterparty_bic  = rng.choice(competitor_bics)
                counterparty_iban = _fake_iban(rng, counterparty_bic)
                is_competitor     = True

            rows.append({
                "transaction_id":         f"TX{tx_id:08d}",
                "customer_id":            cid,
                "transaction_date":       tx_date,
                "amount_eur":             amount,
                "direction":              direction,
                "merchant_category":      category,
                "counterparty_iban":      counterparty_iban,
                "counterparty_bank_bic":  counterparty_bic,
                "channel":                rng.choice(["app", "web", "atm", "branch", "standing_order"], p=[0.40, 0.25, 0.15, 0.05, 0.15]),
                "is_competitor_transfer": is_competitor,
            })
            tx_id += 1

        # ── Forward window (post-snapshot, 60 days) ────────────────────────
        n_fwd = int(rng.integers(30, 90))
        for _ in range(n_fwd):
            tx_date   = SNAPSHOT_DATE + timedelta(days=int(rng.integers(0, 60)))
            direction = rng.choice(["credit", "debit"], p=[0.35, 0.65])
            amount    = round(float(min(rng.lognormal(mean=4.5, sigma=1.2), 25_000.0)), 2)
            category  = rng.choice([
                "salary", "rent", "utilities", "groceries",
                "restaurants", "transport", "online_retail",
                "atm_withdrawal", "transfer", "insurance",
            ], p=[0.08, 0.05, 0.06, 0.12, 0.10, 0.08, 0.15, 0.10, 0.18, 0.08])

            if is_churner and category == "salary" and direction == "credit":
                category  = "transfer"
                direction = "debit"

            if not is_churner and category == "salary" and direction == "credit" and sal:
                amount = round(float(rng.uniform(2_200, 6_500)), 2)

            is_competitor, counterparty_bic, counterparty_iban = False, None, None
            if category == "transfer" and direction == "debit":
                comp_prob = 0.65 if is_churner else 0.20
                if rng.random() < comp_prob:
                    counterparty_bic  = rng.choice(competitor_bics)
                    counterparty_iban = _fake_iban(rng, counterparty_bic)
                    is_competitor     = True

            rows.append({
                "transaction_id":         f"TX{tx_id:08d}",
                "customer_id":            cid,
                "transaction_date":       tx_date,
                "amount_eur":             amount,
                "direction":              direction,
                "merchant_category":      category,
                "counterparty_iban":      counterparty_iban,
                "counterparty_bank_bic":  counterparty_bic,
                "channel":                rng.choice(["app", "web", "atm", "branch", "standing_order"], p=[0.40, 0.25, 0.15, 0.05, 0.15]),
                "is_competitor_transfer": is_competitor,
            })
            tx_id += 1

    return pd.DataFrame(rows)


def _generate_complaints_b(
    customers: pd.DataFrame,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """
    Population B: higher complaint volume, longer resolution times.

    KEY DIFFERENCE vs Population A:
    ~22% of customers have at least one complaint (vs 12%).
    More open complaints — resolution times longer (autumn = higher volume).
    Average resolution: 12–28 days (frequently breaching 14-day SLA).
    """
    rows = []
    complaint_id  = 1
    window_start  = SNAPSHOT_DATE - timedelta(days=90)
    categories    = ["card_dispute", "fee_query", "transfer_error",
                     "product_query", "service_quality", "mortgage_query"]

    for _, cust in customers.iterrows():
        # Population B: 22% of customers have a complaint
        if rng.random() > 0.22:
            continue

        n_complaints = int(rng.choice([1, 2, 3, 4], p=[0.55, 0.28, 0.12, 0.05]))

        for _ in range(n_complaints):
            opened   = window_start + timedelta(days=int(rng.integers(0, 80)))
            category = rng.choice(categories)

            # Population B: more open complaints, longer resolution
            resolved = rng.random() < 0.65
            if resolved:
                resolution_days = int(rng.integers(5, 35))
                closed_date     = opened + timedelta(days=resolution_days)
                status          = "resolved"
            else:
                resolution_days = None
                closed_date     = None
                status          = "open"

            rows.append({
                "complaint_id":    f"CMP{complaint_id:07d}",
                "customer_id":     cust["customer_id"],
                "opened_date":     opened,
                "closed_date":     closed_date,
                "category":        category,
                "status":          status,
                "resolution_days": resolution_days,
            })
            complaint_id += 1

    return pd.DataFrame(rows)


def _generate_nps_responses_b(
    customers: pd.DataFrame,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """
    Population B: NPS skews negative (higher friction in autumn).
    Average NPS: 4–6 (vs 6–8 in Population A).
    """
    rows = []
    window_start = SNAPSHOT_DATE - timedelta(days=180)

    nps_verbatims_positive = [
        "Still happy with the service overall.",
        "App improvements noticed, good work.",
    ]
    nps_verbatims_neutral = [
        "Service is acceptable but fees are increasing.",
        "Waiting to see how my mortgage renewal goes.",
        "Nothing particularly good or bad to report.",
    ]
    nps_verbatims_negative = [
        "Mortgage renewal process was poorly communicated.",
        "Competitor offered better rate at renewal.",
        "Complaint took weeks to resolve — unacceptable.",
        "Fees too high compared to KBC and ING.",
        "Hard to get through to anyone by phone.",
        "App crashed twice this month.",
    ]

    for _, cust in customers.iterrows():
        if rng.random() > 0.55:
            continue

        # Population B: NPS distribution skews negative
        score = int(rng.choice(
            range(0, 11),
            p=[0.05, 0.06, 0.08, 0.10, 0.12, 0.12, 0.12, 0.13, 0.10, 0.07, 0.05],
        ))

        if score >= 8:
            verbatim = rng.choice(nps_verbatims_positive)
        elif score >= 6:
            verbatim = rng.choice(nps_verbatims_neutral)
        else:
            verbatim = rng.choice(nps_verbatims_negative)

        response_date = window_start + timedelta(days=int(rng.integers(0, 180)))

        rows.append({
            "customer_id":   cust["customer_id"],
            "response_date": response_date,
            "score":         score,
            "verbatim_text": verbatim,
        })

    return pd.DataFrame(rows)


def _generate_app_sessions_b(
    customers: pd.DataFrame,
    rng: np.random.Generator,
    churning_ids: set = None,
) -> pd.DataFrame:
    """
    App sessions covering 60 days pre-snapshot and 60 days post-snapshot.

    Population B: lower engagement overall (autumn disengagement).
    Churning customers get zero sessions in the forward window (signal 2).
    """
    rows = []
    hist_start = SNAPSHOT_DATE - timedelta(days=60)

    features_used = [
        "account_overview", "transfer", "pay_bill",
        "savings_overview", "investments", "card_management",
        "statements", "notifications",
    ]

    for _, cust in customers.iterrows():
        cid        = cust["customer_id"]
        seg        = cust["segment"]
        is_churner = churning_ids and cid in churning_ids

        def _session_count():
            if seg == "student":           return int(rng.integers(5, 22))
            elif seg == "starter":         return int(rng.integers(4, 18))
            elif seg == "private_banking": return int(rng.integers(3, 14))
            else:                          return int(rng.integers(3, 16))

        # Historical window
        n_hist = _session_count()
        if rng.random() < 0.15:
            n_hist = 0
        for _ in range(n_hist):
            rows.append({
                "customer_id":              cid,
                "session_date":             hist_start + timedelta(days=int(rng.integers(0, 60))),
                "session_duration_seconds": int(rng.integers(30, 900)),
                "feature_used":             rng.choice(features_used),
            })

        # Forward window — churners get zero sessions (signal 2)
        n_fwd = 0 if is_churner else _session_count()
        for _ in range(n_fwd):
            rows.append({
                "customer_id":              cid,
                "session_date":             SNAPSHOT_DATE + timedelta(days=int(rng.integers(0, 60))),
                "session_duration_seconds": int(rng.integers(30, 900)),
                "feature_used":             rng.choice(features_used),
            })

    return pd.DataFrame(rows)
