"""
feature_transformation.py — Azure ML managed feature store transformation.

Called by the feature store during offline materialization. Receives the
source DataFrame (output of the feature pipeline component) and applies
the final null-filling and label-encoding so the stored features are
model-ready.

The source is the parquet produced by feature_pipeline.py — fields are
already aggregated from SQL. This step standardises nulls and encodes
the two categorical columns so every consumer (training, batch scoring,
online scoring) works from a consistent encoding.
"""

import pandas as pd
from sklearn.preprocessing import LabelEncoder

SEGMENT_CATEGORIES = ["private_banking", "standard", "starter", "student"]
REGION_CATEGORIES  = ["Brussels", "Flanders", "Wallonia"]


def get_features_df(
    source_df: pd.DataFrame,
    feature_window_start: pd.Timestamp,
    feature_window_end: pd.Timestamp,
) -> pd.DataFrame:
    """
    Transform raw aggregated features into model-ready feature vectors.

    Parameters
    ----------
    source_df : pd.DataFrame
        Output of the feature pipeline component — one row per customer.
    feature_window_start, feature_window_end : pd.Timestamp
        The materialization window (used to filter source_df if it spans
        multiple snapshots; Population A has a single snapshot date).

    Returns
    -------
    pd.DataFrame
        Feature-store-ready DataFrame indexed on (customer_id, snapshot_date).
    """
    df = source_df.copy()

    # Filter to the requested materialization window
    if "snapshot_date" in df.columns:
        df["snapshot_date"] = pd.to_datetime(df["snapshot_date"])
        df = df[
            (df["snapshot_date"] >= feature_window_start)
            & (df["snapshot_date"] <= feature_window_end)
        ]

    # ── Null filling ──────────────────────────────────────────────────────────
    df["days_since_last_login"]     = df["days_since_last_login"].fillna(999).astype(int)
    df["competitor_transfer_count"] = df["competitor_transfer_count"].fillna(0).astype(int)
    df["complaints_open"]           = df["complaints_open"].fillna(0).astype(int)
    df["months_to_rate_reset"]      = df["months_to_rate_reset"].fillna(99.0).astype(float)
    df["avg_monthly_inflow_eur"]    = df["avg_monthly_inflow_eur"].fillna(0.0).astype(float)
    df["app_logins_last_30d"]       = df["app_logins_last_30d"].fillna(0).astype(int)
    df["app_logins_last_90d"]       = df["app_logins_last_90d"].fillna(0).astype(int)
    df["salary_account_flag"]       = df["salary_account_flag"].fillna(0).astype(int)
    df["product_count"]             = df["product_count"].fillna(0).astype(int)
    df["nps_score_last"]            = df["nps_score_last"].fillna(5.0).astype(float)

    # ── Categorical encoding (deterministic — sorted categories) ──────────────
    seg_le = LabelEncoder().fit(SEGMENT_CATEGORIES)
    reg_le = LabelEncoder().fit(REGION_CATEGORIES)

    df["segment_enc"] = seg_le.transform(
        df["segment"].fillna("standard").apply(
            lambda x: x if x in SEGMENT_CATEGORIES else "standard"
        )
    )
    df["region_enc"] = reg_le.transform(
        df["region"].fillna("Flanders").apply(
            lambda x: x if x in REGION_CATEGORIES else "Flanders"
        )
    )

    return df
