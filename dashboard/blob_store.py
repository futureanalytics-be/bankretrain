"""
blob_store.py — Read dashboard cache Parquet files from Azure Blob Storage.

The retrain pipeline writes approved_outreach.parquet, compliance_review_queue.parquet,
and customers.parquet to the 'dashboard-cache' container after each SQL write.
The dashboard reads from these files instead of querying Azure SQL directly,
avoiding the need for the Microsoft ODBC Driver on Streamlit Community Cloud.

Auth: DefaultAzureCredential picks up AZURE_CLIENT_ID / AZURE_CLIENT_SECRET /
AZURE_TENANT_ID from os.environ (bootstrapped by config.py from st.secrets).
"""

import io
import json
import os
from typing import Optional

import pandas as pd
import streamlit as st
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

import config  # noqa — bootstraps os.environ from st.secrets

_CONTAINER = "dashboard-cache"


@st.cache_resource(show_spinner=False)
def _blob_service() -> BlobServiceClient:
    cred = DefaultAzureCredential()
    account = os.environ["AZURE_STORAGE_ACCOUNT"]
    return BlobServiceClient(f"https://{account}.blob.core.windows.net", cred)


@st.cache_data(ttl=300, show_spinner="Loading data…")
def _read_parquet(blob_name: str) -> pd.DataFrame:
    data = _blob_service().get_blob_client(_CONTAINER, blob_name).download_blob().readall()
    return pd.read_parquet(io.BytesIO(data))


# ── Public read helpers ───────────────────────────────────────────────────────

def get_customers() -> pd.DataFrame:
    return _read_parquet("customers.parquet")


def get_approved_outreach(batch_date: Optional[str] = None) -> pd.DataFrame:
    df = _read_parquet("approved_outreach.parquet")
    if batch_date:
        df = df[df["batch_date"].astype(str) == batch_date]
    if "message_draft" in df.columns:
        df["message_preview"] = df["message_draft"].str[:500]
        df["total_tokens"] = (
            df.get("agent1_tokens", 0)
            + df.get("agent2_tokens", 0)
            + df.get("agent3_tokens", 0)
        )
    return df.sort_values("approved_at", ascending=False) if "approved_at" in df.columns else df


def get_approved_message(customer_id: str, batch_date: str) -> Optional[str]:
    df = _read_parquet("approved_outreach.parquet")
    mask = (df["customer_id"] == customer_id) & (df["batch_date"].astype(str) == batch_date)
    rows = df[mask]
    return rows["message_draft"].iloc[0] if not rows.empty else None


def get_review_queue(batch_date: Optional[str] = None,
                     status_filter: Optional[str] = None) -> pd.DataFrame:
    df = _read_parquet("compliance_review_queue.parquet")
    if batch_date:
        df = df[df["batch_date"].astype(str) == batch_date]
    if status_filter:
        df = df[df["status"] == status_filter]
    if "message_draft" in df.columns:
        df["message_preview"] = df["message_draft"].str[:500]
    return df.sort_values("created_at", ascending=False) if "created_at" in df.columns else df


def get_queue_message(queue_id: int) -> Optional[dict]:
    df = _read_parquet("compliance_review_queue.parquet")
    rows = df[df["id"] == queue_id]
    if rows.empty:
        return None
    row = rows.iloc[0].to_dict()
    if row.get("violated_rules") and isinstance(row["violated_rules"], str):
        try:
            row["violated_rules"] = json.loads(row["violated_rules"])
        except (json.JSONDecodeError, TypeError):
            pass
    return row


def get_product_holdings() -> pd.DataFrame:
    return _read_parquet("product_holdings.parquet")


def get_customer_features() -> pd.DataFrame:
    return _read_parquet("customer_features.parquet")


def get_batch_summary() -> pd.DataFrame:
    approved = _read_parquet("approved_outreach.parquet")
    queue    = _read_parquet("compliance_review_queue.parquet")

    a = approved.groupby("batch_date").size().rename("approved_count").reset_index()
    r = queue.groupby("batch_date").size().rename("review_count").reset_index()

    df = pd.merge(a, r, on="batch_date", how="outer").fillna(0)
    df["approved_count"] = df["approved_count"].astype(int)
    df["review_count"]   = df["review_count"].astype(int)
    total = df["approved_count"] + df["review_count"]
    df["pass_rate"] = df["approved_count"] / total.replace(0, float("nan"))
    return df.sort_values("batch_date", ascending=False)
