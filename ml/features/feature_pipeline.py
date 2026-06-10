"""
feature_pipeline.py — Azure ML pipeline: SQL → feature store

Defines and submits an AML pipeline job that:
  1. Queries Azure SQL for all 10 churn features (pre-snapshot window)
  2. Outputs the feature table as parquet to Blob Storage
  3. Registers the output as a versioned Azure ML data asset

The AML compute job uses the feature pipeline user-assigned managed identity
(bankretain-mi-featurepipeline-dev) so it can read Azure SQL without passwords.

Usage:
    python ml/features/feature_pipeline.py \
        --subscription-id  <sub-id> \
        --resource-group   bankretain-ml-rg \
        --workspace-name   bankretain-aml-dev-<suffix> \
        --mi-client-id     <feature-pipeline-mi-client-id> \
        --snapshot-date    2025-04-01 \
        --dataset-version  population_a

The script has two modes:
  --submit   Defines and submits the AML pipeline job (default)
  --local    Runs the SQL extraction locally (uses DefaultAzureCredential)
"""

import argparse
import os
import struct
import sys
import time

import pandas as pd
import pyodbc
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential

# ── Feature query ──────────────────────────────────────────────────────────────
# Reads all pre-snapshot-window aggregations for every customer.
# The snapshot date is injected at runtime so the same script works for
# Population A (2025-04-01) and Population B (2025-10-01).

FEATURE_SQL = """
SELECT
    c.customer_id,
    c.snapshot_date,
    CAST(c.churned AS INT)              AS churned,
    CAST(c.salary_account_flag AS INT)  AS salary_account_flag,
    c.segment,
    c.region,

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
GROUP BY c.customer_id, c.snapshot_date, c.churned, c.salary_account_flag,
         c.segment, c.region
"""


# ── SQL connection (managed identity path) ────────────────────────────────────

def _connect(sql_server: str, sql_db: str, mi_client_id: str | None = None) -> pyodbc.Connection:
    if mi_client_id:
        cred = ManagedIdentityCredential(client_id=mi_client_id)
    else:
        cred = DefaultAzureCredential()

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
    # Retry for error 40613 (serverless auto-pause wake-up)
    for attempt in range(1, 4):
        try:
            return pyodbc.connect(conn_str, attrs_before={1256: token_struct}, timeout=60, autocommit=True)
        except pyodbc.Error as e:
            if "40613" in str(e) and attempt < 3:
                print(f"Database waking from auto-pause, retrying in 20s (attempt {attempt}/3)...")
                time.sleep(20)
            else:
                raise


def extract_features(
    sql_server: str,
    sql_db: str,
    snapshot_date: str,
    output_path: str,
    mi_client_id: str | None = None,
) -> None:
    """Query SQL and write features as parquet to output_path."""
    print(f"Connecting to {sql_server}/{sql_db} ...")
    conn   = _connect(sql_server, sql_db, mi_client_id)
    cursor = conn.cursor()

    sql = FEATURE_SQL.format(snap=snapshot_date)
    print(f"Running feature query (snapshot={snapshot_date}) ...")
    cursor.execute(sql)

    columns = [col[0] for col in cursor.description]
    rows    = cursor.fetchall()
    cursor.close()
    conn.close()

    df = pd.DataFrame.from_records(rows, columns=columns)
    print(f"Fetched {len(df):,} rows, {len(df.columns)} columns")

    os.makedirs(output_path, exist_ok=True)
    out_file = os.path.join(output_path, "features.parquet")
    df.to_parquet(out_file, index=False, engine="pyarrow")
    print(f"Written: {out_file}")


# ── AML pipeline submission ────────────────────────────────────────────────────

def submit_pipeline(args) -> None:
    from azure.ai.ml import MLClient, command, Input, Output
    from azure.ai.ml.entities import (
        Environment,
        ManagedIdentityConfiguration,
        ResourceConfiguration,
    )

    client = MLClient(
        credential=DefaultAzureCredential(),
        subscription_id=args.subscription_id,
        resource_group_name=args.resource_group,
        workspace_name=args.workspace_name,
    )

    env = Environment(
        name="bankretain-ml-env",
        description="BankRetain ML pipeline environment",
        conda_file={
            "name": "bankretain-ml",
            "channels": ["conda-forge", "defaults"],
            "dependencies": [
                "python=3.10",
                "pip",
                {"pip": [
                    "azure-ai-ml",
                    "azure-identity",
                    "lightgbm>=4.0",
                    "scikit-learn>=1.3",
                    "pandas>=2.0",
                    "pyodbc",
                    "pyarrow>=13",
                    "mlflow",
                    "matplotlib",
                    "seaborn",
                ]},
            ],
        },
        image="mcr.microsoft.com/azureml/openmpi4.1.0-ubuntu22.04",
    )


    feature_job = command(
        name="feature_extraction",
        display_name="Feature Extraction — SQL to Parquet",
        description="Aggregate 10 churn features from Azure SQL for all customers",
        code=os.path.dirname(os.path.abspath(__file__)),
        command=(
            "python feature_pipeline.py --local "
            "--snapshot-date ${{inputs.snapshot_date}} "
            "--dataset-version ${{inputs.dataset_version}} "
            "--output-path ${{outputs.features_output}}"
        ),
        environment=env,
        inputs={
            "snapshot_date":   Input(type="string", default=args.snapshot_date),
            "dataset_version": Input(type="string", default=args.dataset_version),
        },
        outputs={"features_output": Output(type="uri_folder")},
        environment_variables={
            "BANKRETAIN_SQL_SERVER": args.sql_server,
            "BANKRETAIN_SQL_DB":     args.sql_db,
            "AZURE_CLIENT_ID":       args.mi_client_id,
        },
        resources=ResourceConfiguration(
            instance_type="Standard_DS3_v2",
            instance_count=1,
        ),
        identity=ManagedIdentityConfiguration(client_id=args.mi_client_id),
        experiment_name="bankretain-feature-pipeline",
    )

    submitted = client.jobs.create_or_update(feature_job)
    print(f"Pipeline job submitted: {submitted.name}")
    print(f"Studio URL: {submitted.studio_url}")
    return submitted


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--local",           action="store_true",
                        help="Run SQL extraction locally instead of submitting to AML")
    parser.add_argument("--subscription-id", dest="subscription_id")
    parser.add_argument("--resource-group",  dest="resource_group", default="bankretain-ml-rg")
    parser.add_argument("--workspace-name",  dest="workspace_name")
    parser.add_argument("--sql-server",      dest="sql_server",
                        default=os.environ.get("BANKRETAIN_SQL_SERVER", ""))
    parser.add_argument("--sql-db",          dest="sql_db",
                        default=os.environ.get("BANKRETAIN_SQL_DB", "bankretaindb"))
    parser.add_argument("--mi-client-id",    dest="mi_client_id",
                        default=os.environ.get("AZURE_CLIENT_ID"))
    parser.add_argument("--snapshot-date",   dest="snapshot_date",  default="2025-04-01")
    parser.add_argument("--dataset-version", dest="dataset_version", default="population_a")
    parser.add_argument("--output-path",     dest="output_path",    default="./output/features")
    args = parser.parse_args()

    if args.local:
        extract_features(
            sql_server=args.sql_server,
            sql_db=args.sql_db,
            snapshot_date=args.snapshot_date,
            output_path=args.output_path,
            mi_client_id=args.mi_client_id,
        )
    else:
        if not all([args.subscription_id, args.workspace_name, args.sql_server]):
            print("For AML submission, provide --subscription-id, --workspace-name, --sql-server")
            sys.exit(1)
        submit_pipeline(args)
