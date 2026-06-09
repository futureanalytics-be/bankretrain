"""
label_generator.py — BankRetain churn label computation

Computes churned = 1 for each customer by scanning a 60-day forward
window from the snapshot date. A customer is labelled churned if they
exhibit TWO OR MORE of the following disengagement signals:

  Signal 1: Salary domiciliation stops appearing in inflow transactions
  Signal 2: App logins drop to zero for 30+ consecutive days
  Signal 3: Number of active products reduces by one or more
  Signal 4: Outgoing transfers to a known competitor IBAN exceed 3
            in a rolling 30-day period

Labels are written back onto the customers DataFrame as:
  - churned (bool)
  - churn_signal_count (int)       number of signals fired
  - signal_salary_stop (bool)
  - signal_app_inactive (bool)
  - signal_product_reduction (bool)
  - signal_competitor_transfers (bool)

These signal columns are useful for debugging label quality and for
understanding feature importance in the trained model.
"""

import numpy as np
import pandas as pd
from datetime import timedelta
from typing import Dict

from population_a import COMPETITOR_BICS

COMPETITOR_BIC_SET = set(COMPETITOR_BICS.values())
CHURN_WINDOW_DAYS  = 60
CHURN_SIGNAL_THRESHOLD = 2   # customer is churned if >= 2 signals fire


def compute_churn_labels(data: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    """
    Add churn labels to the customers DataFrame.

    Modifies data['customers'] in place by appending label columns.
    Returns the full data dict with customers updated.
    """
    customers       = data["customers"].copy()
    transactions    = data["transactions"].copy()
    app_sessions    = data["app_sessions"].copy()
    customer_prods  = data["customer_products"].copy()

    # Ensure date columns are pandas Timestamp (datetime64) throughout
    customers["snapshot_date"]       = pd.to_datetime(customers["snapshot_date"])
    transactions["transaction_date"] = pd.to_datetime(transactions["transaction_date"])
    app_sessions["session_date"]     = pd.to_datetime(app_sessions["session_date"])
    customer_prods["start_date"]     = pd.to_datetime(customer_prods["start_date"])
    if "end_date" in customer_prods.columns:
        customer_prods["end_date"]   = pd.to_datetime(customer_prods["end_date"])

    # Pre-index tables by customer_id for performance
    tx_by_customer   = transactions.groupby("customer_id")
    sess_by_customer = app_sessions.groupby("customer_id")
    prod_by_customer = customer_prods.groupby("customer_id")

    signals = []

    for _, cust in customers.iterrows():
        cid           = cust["customer_id"]
        snapshot      = cust["snapshot_date"]
        window_start  = snapshot
        window_end    = snapshot + pd.Timedelta(days=CHURN_WINDOW_DAYS)

        s1 = _signal_salary_stop(cid, snapshot, window_start, window_end, tx_by_customer, cust)
        s2 = _signal_app_inactive(cid, window_start, window_end, sess_by_customer)
        s3 = _signal_product_reduction(cid, window_start, window_end, prod_by_customer)
        s4 = _signal_competitor_transfers(cid, window_start, window_end, tx_by_customer)

        signal_count = sum([s1, s2, s3, s4])

        signals.append({
            "customer_id":               cid,
            "churned":                   signal_count >= CHURN_SIGNAL_THRESHOLD,
            "churn_signal_count":        signal_count,
            "signal_salary_stop":        s1,
            "signal_app_inactive":       s2,
            "signal_product_reduction":  s3,
            "signal_competitor_transfers": s4,
        })

    signal_df = pd.DataFrame(signals)
    customers = customers.merge(signal_df, on="customer_id", how="left")

    data["customers"] = customers
    return data


# ─────────────────────────────────────────────────────────────────────────────
# Signal computations
# ─────────────────────────────────────────────────────────────────────────────

def _signal_salary_stop(
    customer_id: str,
    snapshot: object,
    window_start: object,
    window_end: object,
    tx_by_customer,
    cust_row: pd.Series,
) -> bool:
    """
    Signal 1: Salary domiciliation stops appearing in inflow transactions.

    Only applicable to customers with salary_account_flag = True.
    We check whether salary credits appear in the 60-day window.
    If salary was present in the 90 days BEFORE snapshot but absent
    in the 60-day window, this signal fires.
    """
    if not cust_row.get("salary_account_flag", False):
        return False

    if customer_id not in tx_by_customer.groups:
        return False

    cust_tx = tx_by_customer.get_group(customer_id)

    # Pre-snapshot salary presence (baseline)
    pre_window = snapshot - timedelta(days=90)
    pre_salary = cust_tx[
        (cust_tx["transaction_date"] >= pre_window) &
        (cust_tx["transaction_date"] < snapshot) &
        (cust_tx["merchant_category"] == "salary") &
        (cust_tx["direction"] == "credit")
    ]

    if pre_salary.empty:
        # No salary before snapshot — not applicable
        return False

    # Post-snapshot salary absence
    post_salary = cust_tx[
        (cust_tx["transaction_date"] >= window_start) &
        (cust_tx["transaction_date"] <= window_end) &
        (cust_tx["merchant_category"] == "salary") &
        (cust_tx["direction"] == "credit")
    ]

    return post_salary.empty


def _signal_app_inactive(
    customer_id: str,
    window_start: object,
    window_end: object,
    sess_by_customer,
) -> bool:
    """
    Signal 2: App logins drop to zero for 30+ consecutive days
    within the 60-day forward window.

    We check whether there is any 30-day sub-window within the
    forward window that has zero sessions.
    """
    if customer_id not in sess_by_customer.groups:
        # No sessions at all — counts as inactive for entire window
        return True

    cust_sessions = sess_by_customer.get_group(customer_id)
    window_sessions = cust_sessions[
        (cust_sessions["session_date"] >= window_start) &
        (cust_sessions["session_date"] <= window_end)
    ]

    if window_sessions.empty:
        return True

    # Check for 30-day gap within the window
    session_dates = sorted(window_sessions["session_date"].tolist())

    # Check gap at the start of the window
    first_session = session_dates[0]
    if (first_session - window_start).days >= 30:
        return True

    # Check gaps between consecutive sessions
    for i in range(1, len(session_dates)):
        gap = (session_dates[i] - session_dates[i - 1]).days
        if gap >= 30:
            return True

    # Check gap at the end of the window
    last_session = session_dates[-1]
    if (window_end - last_session).days >= 30:
        return True

    return False


def _signal_product_reduction(
    customer_id: str,
    window_start: object,
    window_end: object,
    prod_by_customer,
) -> bool:
    """
    Signal 3: Number of active products reduces by one or more
    within the 60-day forward window.

    We compare the count of active products at window_start vs window_end.
    A product is considered closed if its end_date falls within the window.
    """
    if customer_id not in prod_by_customer.groups:
        return False

    cust_prods = prod_by_customer.get_group(customer_id)

    # Products active at window start
    active_at_start = cust_prods[
        (cust_prods["start_date"] <= window_start) &
        (
            cust_prods["end_date"].isna() |
            (cust_prods["end_date"] > window_start)
        )
    ]

    # Products that were closed during the window
    closed_in_window = cust_prods[
        cust_prods["end_date"].notna() &
        (cust_prods["end_date"] >= window_start) &
        (cust_prods["end_date"] <= window_end)
    ]

    return len(closed_in_window) >= 1 and len(active_at_start) > 1


def _signal_competitor_transfers(
    customer_id: str,
    window_start: object,
    window_end: object,
    tx_by_customer,
) -> bool:
    """
    Signal 4: Outgoing transfers to a known competitor IBAN exceed 3
    in any rolling 30-day period within the 60-day forward window.
    """
    if customer_id not in tx_by_customer.groups:
        return False

    cust_tx = tx_by_customer.get_group(customer_id)

    competitor_tx = cust_tx[
        (cust_tx["transaction_date"] >= window_start) &
        (cust_tx["transaction_date"] <= window_end) &
        (cust_tx["direction"] == "debit") &
        (cust_tx["counterparty_bank_bic"].isin(COMPETITOR_BIC_SET))
    ].copy()

    if competitor_tx.empty:
        return False

    competitor_tx = competitor_tx.sort_values("transaction_date")
    dates = competitor_tx["transaction_date"].tolist()

    # Sliding 30-day window
    for i, start in enumerate(dates):
        end = start + timedelta(days=30)
        count_in_window = sum(1 for d in dates if start <= d <= end)
        if count_in_window > 3:
            return True

    return False
