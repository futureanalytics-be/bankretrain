"""
batch_score.py — BankRetain weekly batch scoring job

Reads all customers from Azure SQL, computes features, loads the production
churn model from the AML model registry, scores all 50,000 customers, and
writes the high-risk subset (churn_score >= 0.70) to high_risk_batch.csv
in Azure Blob Storage.

Designed to run as a scheduled AML command job (Sunday nights).

Usage:
    python ml/scoring/batch_score.py \
        --subscription-id  <sub-id> \
        --resource-group   bankretain-ml-rg \
        --workspace-name   bankretain-aml-dev-<suffix> \
        --storage-account  bankretainstdev<suffix> \
        --container        bankretain-batch \
        --snapshot-date    2025-04-01
"""

import argparse
import datetime
import io
import os
import struct
import sys
import time
from typing import Optional

import mlflow
import mlflow.lightgbm
import pandas as pd
import pyodbc
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
from azure.storage.blob import BlobServiceClient

CHURN_THRESHOLD  = 0.70
MODEL_NAME       = "bankretain-churn-model"
BATCH_BLOB_NAME  = "high_risk_batch.csv"

SEGMENT_CATEGORIES = ["private_banking", "standard", "starter", "student"]
REGION_CATEGORIES  = ["Brussels", "Flanders", "Wallonia"]

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

FEATURE_SQL = """
SELECT
    c.customer_id,
    c.segment,
    c.region,
    CAST(c.salary_account_flag AS INT)  AS salary_account_flag,

    ISNULL(DATEDIFF(day, MAX(s.session_date), CAST('{snap}' AS DATE)), 999)
                                        AS days_since_last_login,
    ISNULL(SUM(CASE WHEN s.session_date >= DATEADD(day, -30, '{snap}') THEN 1 ELSE 0 END), 0)
                                        AS app_logins_last_30d,
    ISNULL(COUNT(s.id), 0)              AS app_logins_last_90d,

    ISNULL(SUM(CASE WHEN t.is_competitor_transfer = 1 THEN 1 ELSE 0 END), 0)
                                        AS competitor_transfer_count,
    ISNULL(AVG(CASE WHEN t.direction = 'credit' THEN t.amount_eur END), 0.0)
                                        AS avg_monthly_inflow_eur,

    ISNULL(COUNT(DISTINCT CASE WHEN comp.status = 'open' THEN comp.complaint_id END), 0)
                                        AS complaints_open,
    MAX(n.score)                        AS nps_score_last,
    ISNULL(COUNT(DISTINCT CASE WHEN cp.status = 'active' THEN cp.product_id END), 0)
                                        AS product_count,
    MIN(CASE WHEN cp.fixed_rate_end_date IS NOT NULL
             THEN DATEDIFF(month, '{snap}', cp.fixed_rate_end_date) END)
                                        AS months_to_rate_reset

FROM dbo.customers c
LEFT JOIN dbo.app_sessions s
       ON c.customer_id = s.customer_id
      AND s.session_date >= DATEADD(day, -90, '{snap}')
      AND s.session_date <= '{snap}'
LEFT JOIN dbo.transactions t
       ON c.customer_id = t.customer_id
      AND t.transaction_date >= DATEADD(day, -90, '{snap}')
      AND t.transaction_date <= '{snap}'
LEFT JOIN dbo.complaints comp
       ON c.customer_id = comp.customer_id
LEFT JOIN dbo.nps_responses n
       ON c.customer_id = n.customer_id
LEFT JOIN dbo.customer_products cp
       ON c.customer_id = cp.customer_id
GROUP BY c.customer_id, c.segment, c.region, c.salary_account_flag
"""


def _credential(mi_client_id: Optional[str]):
    if mi_client_id:
        return ManagedIdentityCredential(client_id=mi_client_id)
    return DefaultAzureCredential()


def _sql_connect(sql_server: str, sql_db: str, cred) -> pyodbc.Connection:
    token        = cred.get_token("https://database.windows.net/.default")
    token_bytes  = token.token.encode("UTF-16-LE")
    token_struct = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)
    conn_str = (
        f"Driver={{ODBC Driver 18 for SQL Server}};"
        f"Server={sql_server};"
        f"Database={sql_db};"
        f"Encrypt=yes;"
        f"TrustServerCertificate=no;"
    )
    for attempt in range(1, 4):
        try:
            return pyodbc.connect(conn_str, attrs_before={1256: token_struct}, timeout=60, autocommit=True)
        except pyodbc.Error as e:
            if "40613" in str(e) and attempt < 3:
                print(f"Database waking from auto-pause, retrying in 20s (attempt {attempt}/3)...")
                time.sleep(20)
            else:
                raise


def fetch_features(sql_server: str, sql_db: str, snapshot_date: str, cred) -> pd.DataFrame:
    print(f"Fetching features from SQL (snapshot={snapshot_date}) ...")
    conn   = _sql_connect(sql_server, sql_db, cred)
    cursor = conn.cursor()
    cursor.execute(FEATURE_SQL.format(snap=snapshot_date))
    columns = [col[0] for col in cursor.description]
    rows    = cursor.fetchall()
    cursor.close()
    conn.close()

    df = pd.DataFrame.from_records(rows, columns=columns)
    print(f"Fetched {len(df):,} customers")
    return df


def preprocess(df: pd.DataFrame) -> pd.DataFrame:
    from sklearn.preprocessing import LabelEncoder

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


def load_production_model(subscription_id, resource_group, workspace_name, cred):
    import tempfile
    from azure.ai.ml import MLClient

    client = MLClient(cred, subscription_id, resource_group, workspace_name)

    versions = list(client.models.list(name=MODEL_NAME))
    prod_versions = [v for v in versions if v.tags.get("status") == "production"]

    if not prod_versions:
        staging_versions = [v for v in versions if v.tags.get("status") == "staging"]
        if not staging_versions:
            raise RuntimeError(f"No registered model found for {MODEL_NAME}")
        latest = sorted(staging_versions, key=lambda v: int(v.version))[-1]
        print(f"Warning: no production model — using staging version {latest.version}")
    else:
        latest = sorted(prod_versions, key=lambda v: int(v.version))[-1]
        print(f"Production model: {MODEL_NAME} version={latest.version}")

    # Download artifacts to temp dir; avoids azureml:// MLflow URI (needs azureml-mlflow)
    download_path = os.path.join(tempfile.gettempdir(), f"bankretain-model-v{latest.version}")
    model_dir = os.path.join(download_path, MODEL_NAME)
    if not os.path.exists(model_dir):
        client.models.download(name=MODEL_NAME, version=latest.version, download_path=download_path)
    model = mlflow.lightgbm.load_model(model_dir)
    return model, latest.version


def upload_to_blob(df: pd.DataFrame, storage_account: str, container: str, cred) -> None:
    url = f"https://{storage_account}.blob.core.windows.net"
    client = BlobServiceClient(account_url=url, credential=cred)
    container_client = client.get_container_client(container)

    try:
        container_client.create_container()
    except Exception:
        pass  # already exists

    csv_bytes = df.to_csv(index=False).encode("utf-8")
    container_client.upload_blob(
        name=BATCH_BLOB_NAME,
        data=io.BytesIO(csv_bytes),
        overwrite=True,
        content_type="text/csv",
    )
    print(f"Uploaded {BATCH_BLOB_NAME} ({len(df):,} high-risk rows) to {storage_account}/{container}/")


def main(args) -> None:
    cred = _credential(os.environ.get("AZURE_CLIENT_ID"))

    df = fetch_features(args.sql_server, args.sql_db, args.snapshot_date, cred)
    df = preprocess(df)

    model, model_version = load_production_model(
        args.subscription_id, args.resource_group, args.workspace_name, cred
    )

    X = df[FEATURE_COLUMNS]
    df["churn_score"] = model.predict_proba(X)[:, 1]
    df["high_risk"]   = df["churn_score"] >= CHURN_THRESHOLD
    df["model_version"] = model_version
    df["scored_at"]   = pd.Timestamp.utcnow().isoformat()

    high_risk = df[df["high_risk"]].copy()
    print(f"High-risk customers (>= {CHURN_THRESHOLD}): {len(high_risk):,} of {len(df):,}")

    output_cols = ["customer_id", "segment", "region", "churn_score",
                   "model_version", "scored_at"] + FEATURE_COLUMNS
    output_cols = [c for c in output_cols if c in high_risk.columns]

    if args.storage_account:
        upload_to_blob(high_risk[output_cols], args.storage_account, args.container, cred)
    else:
        local_path = os.path.join(args.output_path, BATCH_BLOB_NAME)
        os.makedirs(args.output_path, exist_ok=True)
        high_risk[output_cols].to_csv(local_path, index=False)
        print(f"Written locally: {local_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--subscription-id", dest="subscription_id", required=True)
    parser.add_argument("--resource-group",  dest="resource_group",  default="bankretain-ml-rg")
    parser.add_argument("--workspace-name",  dest="workspace_name",  required=True)
    parser.add_argument("--sql-server",      dest="sql_server",
                        default=os.environ.get("BANKRETAIN_SQL_SERVER", ""))
    parser.add_argument("--sql-db",          dest="sql_db",
                        default=os.environ.get("BANKRETAIN_SQL_DB", "bankretaindb"))
    parser.add_argument("--snapshot-date",   dest="snapshot_date",
                        default=datetime.date.today().isoformat())
    parser.add_argument("--storage-account", dest="storage_account", default="")
    parser.add_argument("--container",       default="bankretain-batch")
    parser.add_argument("--output-path",     dest="output_path",     default="./output/batch")
    args = parser.parse_args()
    main(args)
