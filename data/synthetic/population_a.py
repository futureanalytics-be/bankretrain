"""
population_a.py — BankRetain Population A generator (spring/summer baseline)

Generates 50,000 synthetic Belgian retail banking customers representing
the spring/summer behavioural period. Used to train churn model v1.

Population A characteristics:
  - Mortgage rate resets are rare (fixed rates typically 5–10 year terms,
    resets concentrated away from September)
  - Moderate competitor transfers (~5–8% of customers show this signal)
  - Higher app engagement (regular logins, active digital banking)
  - ~10% churn rate after label computation

All distributions are designed to be realistic for Belgian retail banking
but are not calibrated against real bank data.
"""

import numpy as np
import pandas as pd
from datetime import date, timedelta
from typing import Dict

# Known Belgian bank BICs used for competitor transfer detection
# These are the four dominant retail banks in Belgium
COMPETITOR_BICS = {
    "KBC":              "KREDBEBB",
    "ING Belgium":      "BBRUBEBB",
    "Belfius":          "GKCCBEBB",
    "BNP Paribas Fortis": "GEBABEBB",
}

# Belgian provinces mapped to regions for segmentation
REGIONS = ["Flanders", "Wallonia", "Brussels"]
REGION_WEIGHTS = [0.58, 0.31, 0.11]   # approximate Belgian population distribution

# Customer segments
SEGMENTS = ["student", "starter", "standard", "private_banking"]
SEGMENT_WEIGHTS = [0.10, 0.20, 0.60, 0.10]

# Product types offered
PRODUCT_TYPES = [
    "current_account",
    "savings_account",
    "mortgage",
    "consumer_credit",
    "investment",
    "insurance",
]

SNAPSHOT_DATE    = date(2025, 4, 1)          # Population A snapshot: spring
FORWARD_END_DATE = date(2025, 5, 31)         # 60 days after snapshot (label window end)


def generate_population_a(n_customers: int = 50_000, random_seed: int = 42) -> Dict[str, pd.DataFrame]:
    """
    Generate Population A synthetic data.

    Returns a dict of DataFrames matching the Azure SQL schema:
        customers, products, customer_products,
        transactions, complaints, nps_responses,
        app_sessions, branch_visits
    """
    rng = np.random.default_rng(random_seed)

    customers = _generate_customers(n_customers, rng)

    # Pre-assign exactly 10% of customers as churners so the label
    # generator produces the expected ~10% churn rate. Forward-window
    # data is generated differently for churners to ensure 2+ signals fire.
    churn_idx    = rng.choice(n_customers, size=int(n_customers * 0.10), replace=False)
    churning_ids = set(customers.iloc[churn_idx]["customer_id"])

    products       = _generate_products()
    customer_prods = _generate_customer_products(customers, products, rng, churning_ids)
    transactions   = _generate_transactions(customers, customer_prods, rng, population="a", churning_ids=churning_ids)
    complaints     = _generate_complaints(customers, rng, population="a")
    nps            = _generate_nps_responses(customers, rng, population="a")
    app_sessions   = _generate_app_sessions(customers, rng, population="a", churning_ids=churning_ids)
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
# Table generators
# ─────────────────────────────────────────────────────────────────────────────

def _generate_customers(n: int, rng: np.random.Generator) -> pd.DataFrame:
    """Core customer master table."""
    customer_ids = [f"C{i:06d}" for i in range(1, n + 1)]

    # Age distribution: 18–75, roughly normal centred at 42
    ages = rng.integers(18, 75, size=n)

    regions  = rng.choice(REGIONS,   size=n, p=REGION_WEIGHTS)
    segments = rng.choice(SEGMENTS,  size=n, p=SEGMENT_WEIGHTS)

    # Tenure: 30 days to 25 years, right-skewed (most customers are mid-tenure)
    tenure_days = rng.integers(30, 25 * 365, size=n)
    customer_since = [
        SNAPSHOT_DATE - timedelta(days=int(d)) for d in tenure_days
    ]

    # Preferred language: Flemish-heavy, matching region distribution
    preferred_language = []
    for region in regions:
        if region == "Flanders":
            preferred_language.append(rng.choice(["nl", "en"], p=[0.90, 0.10]))
        elif region == "Wallonia":
            preferred_language.append(rng.choice(["fr", "en"], p=[0.88, 0.12]))
        else:  # Brussels
            preferred_language.append(rng.choice(["nl", "fr", "en"], p=[0.40, 0.45, 0.15]))

    # Salary account flag — most standard/private customers have salary domiciled
    salary_flags = []
    for seg in segments:
        if seg in ("standard", "private_banking"):
            salary_flags.append(bool(rng.choice([True, False], p=[0.82, 0.18])))
        elif seg == "starter":
            salary_flags.append(bool(rng.choice([True, False], p=[0.65, 0.35])))
        else:  # student
            salary_flags.append(bool(rng.choice([True, False], p=[0.30, 0.70])))

    # Relationship manager assigned for private banking only
    rm_ids = [
        f"RM{rng.integers(1, 20):03d}" if seg == "private_banking" else None
        for seg in segments
    ]

    return pd.DataFrame({
        "customer_id":          customer_ids,
        "snapshot_date":        SNAPSHOT_DATE,
        "age":                  ages,
        "region":               regions,
        "segment":              segments,
        "customer_since_date":  customer_since,
        "preferred_language":   preferred_language,
        "salary_account_flag":  salary_flags,
        "relationship_manager_id": rm_ids,
    })


def _generate_products() -> pd.DataFrame:
    """Static product master — same for both populations."""
    return pd.DataFrame({
        "product_id":   [f"P{i:03d}" for i in range(1, len(PRODUCT_TYPES) + 1)],
        "product_type": PRODUCT_TYPES,
        "product_name": [
            "FlexAccount Current Account",
            "SavePlus Savings Account",
            "HomeSecure Mortgage",
            "FlexCredit Consumer Loan",
            "GrowthPlan Investment Account",
            "SecureLife Insurance Package",
        ],
    })


def _generate_customer_products(
    customers: pd.DataFrame,
    products: pd.DataFrame,
    rng: np.random.Generator,
    churning_ids: set = None,
) -> pd.DataFrame:
    """
    Customer-product holdings.

    Rules:
    - Every customer has a current account (entry product)
    - Savings account: 70% of customers
    - Mortgage: segment-dependent, Population A: resets rare
    - Consumer credit: 25% of non-student customers
    - Investment: 40% of private banking, 10% of standard
    - Insurance: 35% of customers with mortgage
    """
    rows = []
    product_map = dict(zip(products["product_type"], products["product_id"]))

    for _, cust in customers.iterrows():
        cid = cust["customer_id"]
        seg = cust["segment"]
        since = cust["customer_since_date"]

        # Current account — always active
        rows.append(_product_row(cid, product_map["current_account"], since, rng, status="active"))

        # Savings account
        if rng.random() < 0.70:
            rows.append(_product_row(cid, product_map["savings_account"], since, rng))

        # Mortgage — Population A: low reset proximity
        if seg in ("standard", "private_banking") and rng.random() < 0.35:
            # Fixed rate end date: mostly 3–10 years away (spring = not renewal season)
            months_to_reset = int(rng.integers(36, 120))
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

        # Insurance — linked to mortgage ownership
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


def _product_row(
    customer_id: str,
    product_id: str,
    since: date,
    rng: np.random.Generator,
    status: str = "active",
    fixed_rate_end_date=None,
) -> dict:
    start = since + timedelta(days=int(rng.integers(0, 180)))
    return {
        "customer_id":          customer_id,
        "product_id":           product_id,
        "start_date":           start,
        "end_date":             None,
        "status":               status,
        "fixed_rate_end_date":  fixed_rate_end_date,
    }


def _generate_transactions(
    customers: pd.DataFrame,
    customer_products: pd.DataFrame,
    rng: np.random.Generator,
    population: str = "a",
    churning_ids: set = None,
) -> pd.DataFrame:
    """
    Transaction history covering 90 days pre-snapshot and 60 days post-snapshot.

    Population A:
    - Regular salary inflows for salary_account_flag customers
    - Moderate competitor transfers (~5–8% of customers show 1–2 transfers)
    - Normal daily banking activity
    - Churning customers: salary stops and high competitor transfers in forward window
    """
    rows = []
    hist_start   = SNAPSHOT_DATE - timedelta(days=90)
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
            if category == "transfer" and direction == "debit" and rng.random() < 0.06:
                counterparty_bic  = rng.choice(competitor_bics)
                counterparty_iban = _fake_iban(rng, counterparty_bic)
                is_competitor     = True

            rows.append({
                "transaction_id":        f"TX{tx_id:08d}",
                "customer_id":           cid,
                "transaction_date":      tx_date,
                "amount_eur":            amount,
                "direction":             direction,
                "merchant_category":     category,
                "counterparty_iban":     counterparty_iban,
                "counterparty_bank_bic": counterparty_bic,
                "channel":               rng.choice(["app", "web", "atm", "branch", "standing_order"], p=[0.40, 0.25, 0.15, 0.05, 0.15]),
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

            # Churners: suppress salary in forward window (signal 1)
            if is_churner and category == "salary" and direction == "credit":
                category  = "transfer"
                direction = "debit"

            if not is_churner and category == "salary" and direction == "credit" and sal:
                amount = round(float(rng.uniform(2_200, 6_500)), 2)

            is_competitor, counterparty_bic, counterparty_iban = False, None, None
            if category == "transfer" and direction == "debit":
                # Churners: high competitor transfer rate in forward window (signal 4)
                comp_prob = 0.60 if is_churner else 0.06
                if rng.random() < comp_prob:
                    counterparty_bic  = rng.choice(competitor_bics)
                    counterparty_iban = _fake_iban(rng, counterparty_bic)
                    is_competitor     = True

            rows.append({
                "transaction_id":        f"TX{tx_id:08d}",
                "customer_id":           cid,
                "transaction_date":      tx_date,
                "amount_eur":            amount,
                "direction":             direction,
                "merchant_category":     category,
                "counterparty_iban":     counterparty_iban,
                "counterparty_bank_bic": counterparty_bic,
                "channel":               rng.choice(["app", "web", "atm", "branch", "standing_order"], p=[0.40, 0.25, 0.15, 0.05, 0.15]),
                "is_competitor_transfer": is_competitor,
            })
            tx_id += 1

    return pd.DataFrame(rows)


def _generate_complaints(
    customers: pd.DataFrame,
    rng: np.random.Generator,
    population: str = "a",
) -> pd.DataFrame:
    """
    Population A: low complaint volume, reasonable resolution times.
    ~12% of customers have at least one complaint in the past 90 days.
    Average resolution: 8–14 days (within SLA).
    """
    rows = []
    complaint_id = 1
    window_start = SNAPSHOT_DATE - timedelta(days=90)

    categories = ["card_dispute", "fee_query", "transfer_error", "product_query", "service_quality"]

    for _, cust in customers.iterrows():
        # Population A: 12% of customers have a complaint
        if rng.random() > 0.12:
            continue

        n_complaints = int(rng.choice([1, 2, 3], p=[0.70, 0.22, 0.08]))

        for _ in range(n_complaints):
            opened = window_start + timedelta(days=int(rng.integers(0, 80)))
            category = rng.choice(categories)

            # Population A: most complaints resolved within SLA (14 days)
            resolved = rng.random() < 0.85
            if resolved:
                resolution_days = int(rng.integers(2, 14))
                closed_date = opened + timedelta(days=resolution_days)
                status = "resolved"
            else:
                resolution_days = None
                closed_date = None
                status = "open"

            rows.append({
                "complaint_id":      f"CMP{complaint_id:07d}",
                "customer_id":       cust["customer_id"],
                "opened_date":       opened,
                "closed_date":       closed_date,
                "category":          category,
                "status":            status,
                "resolution_days":   resolution_days,
            })
            complaint_id += 1

    return pd.DataFrame(rows)


def _generate_nps_responses(
    customers: pd.DataFrame,
    rng: np.random.Generator,
    population: str = "a",
) -> pd.DataFrame:
    """
    Population A: NPS skews positive (spring = low friction period).
    ~55% of customers have a recent NPS response (last 6 months).
    Average NPS: 6–8.
    """
    rows = []
    window_start = SNAPSHOT_DATE - timedelta(days=180)

    nps_verbatims_positive = [
        "Happy with the app, very easy to use.",
        "Good service at branch, staff helpful.",
        "Competitive mortgage rate, satisfied overall.",
        "Fast card replacement, impressed.",
        "Online banking works well for my needs.",
    ]
    nps_verbatims_neutral = [
        "Nothing outstanding but no issues either.",
        "Service is fine. Could improve waiting times.",
        "App is okay. Would like more features.",
    ]
    nps_verbatims_negative = [
        "Fee increase not communicated properly.",
        "Took too long to resolve my complaint.",
        "Hard to reach customer service by phone.",
    ]

    for _, cust in customers.iterrows():
        if rng.random() > 0.55:
            continue

        # Population A: NPS distribution skews positive
        score = int(rng.choice(
            range(0, 11),
            p=[0.01, 0.01, 0.02, 0.03, 0.04, 0.06, 0.10, 0.18, 0.22, 0.18, 0.15],
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


def _generate_app_sessions(
    customers: pd.DataFrame,
    rng: np.random.Generator,
    population: str = "a",
    churning_ids: set = None,
) -> pd.DataFrame:
    """
    App sessions covering 60 days pre-snapshot and 60 days post-snapshot.

    Population A: higher digital engagement (spring/summer = active period).
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
            if seg == "student":        return int(rng.integers(10, 35))
            elif seg == "starter":      return int(rng.integers(8, 28))
            elif seg == "private_banking": return int(rng.integers(5, 20))
            else:                       return int(rng.integers(6, 25))

        # Historical window sessions (pre-snapshot)
        n_hist = _session_count()
        if rng.random() < 0.05:
            n_hist = 0
        for _ in range(n_hist):
            rows.append({
                "customer_id":              cid,
                "session_date":             hist_start + timedelta(days=int(rng.integers(0, 60))),
                "session_duration_seconds": int(rng.integers(30, 900)),
                "feature_used":             rng.choice(features_used),
            })

        # Forward window sessions (post-snapshot)
        # Churners: zero sessions → signal 2 fires
        n_fwd = 0 if is_churner else _session_count()
        for _ in range(n_fwd):
            rows.append({
                "customer_id":              cid,
                "session_date":             SNAPSHOT_DATE + timedelta(days=int(rng.integers(0, 60))),
                "session_duration_seconds": int(rng.integers(30, 900)),
                "feature_used":             rng.choice(features_used),
            })

    return pd.DataFrame(rows)


def _generate_branch_visits(
    customers: pd.DataFrame,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """
    Branch visits: low frequency (digital-first era).
    ~20% of customers have at least one branch visit in 90 days.
    """
    rows = []
    window_start = SNAPSHOT_DATE - timedelta(days=90)
    purposes = ["account_query", "mortgage_advice", "complaint", "product_enquiry", "general"]

    for _, cust in customers.iterrows():
        if rng.random() > 0.20:
            continue

        n_visits = int(rng.choice([1, 2, 3], p=[0.70, 0.22, 0.08]))
        for _ in range(n_visits):
            visit_date = window_start + timedelta(days=int(rng.integers(0, 90)))
            rows.append({
                "customer_id": cust["customer_id"],
                "visit_date":  visit_date,
                "branch_id":   f"BR{rng.integers(1, 50):03d}",
                "purpose":     rng.choice(purposes),
            })

    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _fake_iban(rng: np.random.Generator, bic: str) -> str:
    """Generate a plausible-looking Belgian IBAN for a given BIC."""
    country = "BE"
    check = rng.integers(10, 99)
    account = rng.integers(1_000_000_000_000, 9_999_999_999_999)
    return f"{country}{check}{account}"
