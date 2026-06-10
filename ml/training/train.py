"""
train.py — BankRetain LightGBM churn model training

Reads the feature dataset (parquet output of feature_pipeline), trains a
gradient boosting binary classifier, logs all MLflow artefacts, and saves
the model + evaluation metrics to model_output/.

evaluate.py (next pipeline step) reads metrics.json and decides whether
to register the model.

Usage (local or AML command component):
    python ml/training/train.py \
        --features-path ./output/features \
        --model-output  ./output/model
"""

import argparse
import json
import os

import lightgbm as lgb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mlflow
import mlflow.lightgbm
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

SNAPSHOT_DATE    = "2025-04-01"
CHURN_THRESHOLD  = 0.70
DATASET_VERSION  = os.environ.get("DATASET_VERSION", "population_a")

SEGMENT_CATEGORIES = ["private_banking", "standard", "starter", "student"]
REGION_CATEGORIES  = ["Brussels", "Flanders", "Wallonia"]

NUMERIC_FEATURES = [
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
]
CAT_FEATURES = ["segment_enc", "region_enc"]
ALL_FEATURES = NUMERIC_FEATURES + CAT_FEATURES
TARGET       = "churned"

LGBM_PARAMS = {
    "objective":       "binary",
    "metric":          "binary_logloss",
    "boosting_type":   "gbdt",
    "n_estimators":    500,
    "max_depth":       6,
    "learning_rate":   0.05,
    "num_leaves":      31,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq":    5,
    "lambda_l1":       0.1,
    "lambda_l2":       0.1,
    "min_child_samples": 20,
    "random_state":    42,
    "n_jobs":          -1,
    "verbose":         -1,
}


# ── Data loading ───────────────────────────────────────────────────────────────

def load_features(path: str) -> pd.DataFrame:
    files = [
        os.path.join(path, f) for f in os.listdir(path) if f.endswith(".parquet")
    ]
    if not files:
        raise FileNotFoundError(f"No parquet files found in {path}")
    return pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)


def preprocess(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

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


# ── Artefacts ──────────────────────────────────────────────────────────────────

def _plot_confusion_matrix(y_true, y_pred) -> plt.Figure:
    cm  = confusion_matrix(y_true, y_pred)
    fig, ax = plt.subplots(figsize=(5, 4))
    sns.heatmap(
        cm, annot=True, fmt="d", cmap="Blues", ax=ax,
        xticklabels=["Not Churned", "Churned"],
        yticklabels=["Not Churned", "Churned"],
    )
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Actual")
    ax.set_title(f"Confusion Matrix — threshold={CHURN_THRESHOLD}")
    fig.tight_layout()
    return fig


def _plot_feature_importance(model) -> plt.Figure:
    imp = pd.DataFrame(
        {"feature": ALL_FEATURES, "importance": model.feature_importances_}
    ).sort_values("importance", ascending=True)

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.barh(imp["feature"], imp["importance"], color="#4C9BE8")
    ax.set_xlabel("Importance (split gain)")
    ax.set_title("Feature Importance — LightGBM Churn Model")
    fig.tight_layout()
    return fig


# ── Main training loop ─────────────────────────────────────────────────────────

def train(features_path: str, model_output: str) -> None:
    os.makedirs(model_output, exist_ok=True)

    # AML sets MLFLOW_TRACKING_URI=azureml://... and MLFLOW_RUN_ID pointing to a run
    # that only exists in the azureml store. Without azureml-mlflow, both fail.
    # Override to local file tracking and clear the AML-injected run/experiment IDs.
    if os.environ.get("MLFLOW_TRACKING_URI", "").startswith("azureml://"):
        mlflow.set_tracking_uri("file:./mlruns")
        os.environ.pop("MLFLOW_RUN_ID", None)
        os.environ.pop("MLFLOW_EXPERIMENT_ID", None)

    mlflow.start_run()

    df = load_features(features_path)
    df = preprocess(df)

    X = df[ALL_FEATURES]
    y = df[TARGET].astype(int)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y,
    )

    mlflow.log_params({
        **LGBM_PARAMS,
        "churn_threshold":     CHURN_THRESHOLD,
        "dataset_version":     DATASET_VERSION,
        "snapshot_date":       SNAPSHOT_DATE,
        "feature_set_version": "1",
        "model_type":          "lightgbm",
        "train_size":          len(X_train),
        "test_size":           len(X_test),
    })

    model = lgb.LGBMClassifier(**LGBM_PARAMS)
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        callbacks=[
            lgb.early_stopping(50, verbose=False),
            lgb.log_evaluation(-1),
        ],
    )

    y_proba = model.predict_proba(X_test)[:, 1]
    y_pred  = (y_proba >= CHURN_THRESHOLD).astype(int)

    n_neg = (y_test == 0).sum()
    fp    = ((y_pred == 1) & (y_test == 0)).sum()

    metrics = {
        "precision":          round(float(precision_score(y_test, y_pred, zero_division=0)), 4),
        "recall":             round(float(recall_score(y_test, y_pred, zero_division=0)), 4),
        "f1":                 round(float(f1_score(y_test, y_pred, zero_division=0)), 4),
        "auc":                round(float(roc_auc_score(y_test, y_proba)), 4),
        "false_positive_rate": round(float(fp / n_neg) if n_neg else 0.0, 4),
    }
    mlflow.log_metrics(metrics)

    print(f"\nTest metrics (threshold={CHURN_THRESHOLD}):")
    for k, v in metrics.items():
        print(f"  {k}: {v}")
    print(f"\n{classification_report(y_test, y_pred, target_names=['Not Churned', 'Churned'])}")

    mlflow.log_figure(_plot_confusion_matrix(y_test, y_pred), "confusion_matrix.png")
    mlflow.log_figure(_plot_feature_importance(model),         "feature_importance.png")
    plt.close("all")

    mlflow.lightgbm.save_model(model, model_output)

    with open(os.path.join(model_output, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)

    mlflow.end_run()
    print(f"\nModel saved to: {model_output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--features-path", required=True)
    parser.add_argument("--model-output",  required=True)
    args = parser.parse_args()
    train(args.features_path, args.model_output)
