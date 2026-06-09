"""
score.py — BankRetain managed online endpoint scoring script

Loaded by Azure ML managed online endpoint.
init() runs once at container start; run() handles each inference request.

Request format (JSON):
  Single:  {"customer_id": "C001234", "features": {<feature dict>}}
  Batch:   [{"customer_id": ..., "features": {...}}, ...]

Response format (JSON):
  [{"customer_id": "C001234", "churn_score": 0.83, "high_risk": true}]
"""

import json
import logging
import os

import mlflow.pyfunc
import pandas as pd

log = logging.getLogger(__name__)

CHURN_THRESHOLD = 0.70

FEATURE_COLUMNS = [
    "days_since_last_login",
    "competitor_transfer_count",
    "complaints_open",
    "months_to_rate_reset",
    "avg_monthly_inflow_eur",
    "app_logins_last_30d",
    "app_logins_last_90d",
    "salary_account_flag",
    "product_count",
    "nps_score_last",
    "segment_enc",
    "region_enc",
]

FEATURE_DEFAULTS = {
    "days_since_last_login":    999,
    "competitor_transfer_count": 0,
    "complaints_open":          0,
    "months_to_rate_reset":     99.0,
    "avg_monthly_inflow_eur":   0.0,
    "app_logins_last_30d":      0,
    "app_logins_last_90d":      0,
    "salary_account_flag":      0,
    "product_count":            0,
    "nps_score_last":           5.0,
    "segment_enc":              2,   # "standard" index in sorted label encoding
    "region_enc":               1,   # "Flanders" index
}

_model = None


def init():
    global _model
    model_dir = os.environ.get("AZUREML_MODEL_DIR", ".")
    _model = mlflow.pyfunc.load_model(model_dir)
    log.info("Model loaded from %s", model_dir)


def run(raw_data: str) -> str:
    payload = json.loads(raw_data)

    if isinstance(payload, dict):
        payload = [payload]

    results = []
    for item in payload:
        customer_id = item.get("customer_id", "unknown")
        features    = item.get("features", {})

        row = {col: features.get(col, FEATURE_DEFAULTS[col]) for col in FEATURE_COLUMNS}
        df  = pd.DataFrame([row])

        churn_score = float(_model.predict(df)[0])
        results.append({
            "customer_id": customer_id,
            "churn_score": round(churn_score, 4),
            "high_risk":   churn_score >= CHURN_THRESHOLD,
        })

    return json.dumps(results)
