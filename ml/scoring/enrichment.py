"""
enrichment.py — BankRetain AI Search enrichment pipeline (Phase 3, step 3.1)

Reads high_risk_batch.csv from Blob Storage, queries Azure SQL for customer
context, builds deterministic narrative summaries, and upserts documents to
the Azure AI Search customer-profiles index.  Removes profiles for customers
who are no longer in the high-risk batch.

Run weekly after batch_score.py (Sunday nights), via submit_enrichment.py.

Usage:
    python ml/scoring/enrichment.py \
        --subscription-id  <sub-id> \
        --storage-account  bankretainstdev<suffix> \
        --keyvault-name    bankretain-kv-ai-<suffix> \
        --search-endpoint  https://bankretain-search-dev-<suffix>.search.windows.net
"""

import argparse
import io
import math
import os
import struct
import time
from typing import Optional

import pandas as pd
import pyodbc
from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
from azure.keyvault.secrets import SecretClient
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SimpleField,
)
from azure.storage.blob import BlobServiceClient

INDEX_NAME        = "customer-profiles"
BATCH_BLOB_NAME   = "high_risk_batch.csv"
BATCH_CONTAINER   = "bankretain-batch"
SEARCH_KEY_SECRET = "search-admin-key"

PRODUCT_QUERY = """
SELECT cp.customer_id, p.product_name, p.product_type, cp.fixed_rate_end_date
FROM   dbo.customer_products cp
JOIN   dbo.products p ON cp.product_id = p.product_id
WHERE  cp.customer_id IN ({placeholders})
  AND  cp.status = 'active'
"""

ENGAGEMENT_QUERY = """
SELECT customer_id,
       COUNT(*)                       AS sessions_60d,
       MAX(session_date)              AS last_session,
       AVG(session_duration_seconds)  AS avg_duration_sec
FROM   dbo.app_sessions
WHERE  customer_id IN ({placeholders})
  AND  session_date >= DATEADD(day, -60, GETDATE())
GROUP  BY customer_id
"""

COMPLAINT_QUERY = """
SELECT customer_id,
       COUNT(*)           AS open_count,
       MIN(opened_date)   AS oldest_open,
       MAX(category)      AS last_category
FROM   dbo.complaints
WHERE  customer_id IN ({placeholders})
  AND  status = 'open'
GROUP  BY customer_id
"""

TRANSACTION_QUERY = """
SELECT customer_id,
       COUNT(*)                                                      AS tx_count_90d,
       ISNULL(SUM(CASE WHEN direction = 'credit' THEN amount_eur ELSE 0 END), 0)
                                                                    AS total_inflow_eur,
       SUM(CASE WHEN is_competitor_transfer = 1 THEN 1 ELSE 0 END) AS competitor_transfers,
       MAX(transaction_date)                                         AS last_tx_date
FROM   dbo.transactions
WHERE  customer_id IN ({placeholders})
  AND  transaction_date >= DATEADD(day, -90, GETDATE())
GROUP  BY customer_id
"""


# ── Auth ──────────────────────────────────────────────────────────────────────

def _credential(mi_client_id: Optional[str]):
    if mi_client_id:
        return ManagedIdentityCredential(client_id=mi_client_id)
    return DefaultAzureCredential()


# ── SQL ───────────────────────────────────────────────────────────────────────

def _sql_connect(sql_server: str, sql_db: str, cred) -> pyodbc.Connection:
    token        = cred.get_token("https://database.windows.net/.default")
    token_bytes  = token.token.encode("UTF-16-LE")
    token_struct = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)
    conn_str = (
        f"Driver={{ODBC Driver 18 for SQL Server}};"
        f"Server={sql_server};"
        f"Database={sql_db};"
        f"Encrypt=yes;TrustServerCertificate=no;"
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


def _batch_query(cursor, query_template: str, ids: list, chunk_size: int = 500) -> pd.DataFrame:
    """Run a parameterised IN-clause query in chunks; return combined DataFrame."""
    frames = []
    for i in range(0, len(ids), chunk_size):
        chunk = ids[i : i + chunk_size]
        placeholders = ",".join(["?" for _ in chunk])
        sql = query_template.format(placeholders=placeholders)
        cursor.execute(sql, chunk)
        cols = [col[0] for col in cursor.description]
        frames.append(pd.DataFrame.from_records(cursor.fetchall(), columns=cols))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def fetch_sql_context(sql_server: str, sql_db: str, customer_ids: list, cred) -> dict:
    """Return dict of DataFrames keyed by summary type for all customer_ids."""
    print(f"Querying SQL context for {len(customer_ids):,} customers ...")
    conn   = _sql_connect(sql_server, sql_db, cred)
    cursor = conn.cursor()

    products     = _batch_query(cursor, PRODUCT_QUERY,     customer_ids)
    engagement   = _batch_query(cursor, ENGAGEMENT_QUERY,  customer_ids)
    complaints   = _batch_query(cursor, COMPLAINT_QUERY,   customer_ids)
    transactions = _batch_query(cursor, TRANSACTION_QUERY, customer_ids)

    cursor.close()
    conn.close()
    return {
        "products":     products,
        "engagement":   engagement,
        "complaints":   complaints,
        "transactions": transactions,
    }


# ── Summary builders ──────────────────────────────────────────────────────────

def _product_summary(cid: str, products_df: pd.DataFrame) -> str:
    rows = products_df[products_df["customer_id"] == cid]
    if rows.empty:
        return "No active products."
    parts = []
    for _, r in rows.iterrows():
        name = r["product_name"] or r["product_type"] or "Unknown"
        parts.append(name)
        if pd.notna(r.get("fixed_rate_end_date")):
            parts[-1] += f" (fixed rate ends {r['fixed_rate_end_date']})"
    n = len(parts)
    return f"Active products ({n}): {'; '.join(parts)}."


def _engagement_summary(cid: str, engagement_df: pd.DataFrame) -> str:
    row = engagement_df[engagement_df["customer_id"] == cid]
    if row.empty:
        return "No app sessions in the last 60 days."
    r = row.iloc[0]
    sessions = int(r["sessions_60d"]) if pd.notna(r["sessions_60d"]) else 0
    last     = str(r["last_session"])[:10] if pd.notna(r.get("last_session")) else "unknown"
    avg_sec  = float(r["avg_duration_sec"]) if pd.notna(r.get("avg_duration_sec")) else 0
    avg_min  = round(avg_sec / 60, 1)
    return f"{sessions} app session(s) in the last 60 days (avg {avg_min} min). Last login: {last}."


def _complaint_summary(cid: str, complaints_df: pd.DataFrame) -> str:
    row = complaints_df[complaints_df["customer_id"] == cid]
    if row.empty:
        return "No open complaints."
    r = row.iloc[0]
    n        = int(r["open_count"]) if pd.notna(r["open_count"]) else 0
    oldest   = str(r["oldest_open"])[:10] if pd.notna(r.get("oldest_open")) else "unknown"
    category = r.get("last_category") or "unspecified"
    return f"{n} open complaint(s). Oldest opened: {oldest}. Category: {category}."


def _transaction_summary(cid: str, transactions_df: pd.DataFrame) -> str:
    row = transactions_df[transactions_df["customer_id"] == cid]
    if row.empty:
        return "No transactions in the last 90 days."
    r           = row.iloc[0]
    tx_count    = int(r["tx_count_90d"])     if pd.notna(r["tx_count_90d"])    else 0
    inflow      = float(r["total_inflow_eur"]) if pd.notna(r["total_inflow_eur"]) else 0.0
    competitor  = int(r["competitor_transfers"]) if pd.notna(r["competitor_transfers"]) else 0
    last_tx     = str(r["last_tx_date"])[:10] if pd.notna(r.get("last_tx_date")) else "unknown"
    return (
        f"{tx_count} transaction(s) in last 90 days. "
        f"Total inflow: €{inflow:,.0f}. "
        f"Competitor transfers: {competitor}. "
        f"Last transaction: {last_tx}."
    )


# ── Blob Storage ──────────────────────────────────────────────────────────────

def read_high_risk_batch(storage_account: str, container: str, cred) -> pd.DataFrame:
    url    = f"https://{storage_account}.blob.core.windows.net"
    client = BlobServiceClient(account_url=url, credential=cred)
    blob   = client.get_blob_client(container=container, blob=BATCH_BLOB_NAME)
    data   = blob.download_blob().readall()
    df     = pd.read_csv(io.BytesIO(data))
    print(f"Loaded {len(df):,} high-risk customers from {BATCH_BLOB_NAME}")
    return df


# ── Azure AI Search ───────────────────────────────────────────────────────────

def _index_schema() -> SearchIndex:
    fields = [
        SimpleField(name="customer_id",           type=SearchFieldDataType.String,  key=True,  filterable=True),
        SimpleField(name="snapshot_date",          type=SearchFieldDataType.String,  filterable=True),
        SimpleField(name="churn_score",            type=SearchFieldDataType.Double,  filterable=True, sortable=True),
        SimpleField(name="days_since_last_login",  type=SearchFieldDataType.Int32,   filterable=True),
        SimpleField(name="complaints_open",        type=SearchFieldDataType.Int32,   filterable=True),
        SimpleField(name="competitor_transfer_cnt",type=SearchFieldDataType.Int32,   filterable=True),
        SimpleField(name="months_to_rate_reset",   type=SearchFieldDataType.Double,  filterable=True),
        SimpleField(name="segment",                type=SearchFieldDataType.String,  filterable=True, facetable=True),
        SimpleField(name="region",                 type=SearchFieldDataType.String,  filterable=True, facetable=True),
        SearchField(name="product_summary",     type=SearchFieldDataType.String,  searchable=True),
        SearchField(name="engagement_summary",  type=SearchFieldDataType.String,  searchable=True),
        SearchField(name="complaint_summary",   type=SearchFieldDataType.String,  searchable=True),
        SearchField(name="transaction_summary", type=SearchFieldDataType.String,  searchable=True),
    ]
    return SearchIndex(name=INDEX_NAME, fields=fields)


def ensure_index(endpoint: str, api_key: str) -> None:
    index_client = SearchIndexClient(endpoint, AzureKeyCredential(api_key))
    existing = [idx.name for idx in index_client.list_indexes()]
    if INDEX_NAME in existing:
        print(f"Index '{INDEX_NAME}' already exists — skipping creation.")
    else:
        index_client.create_index(_index_schema())
        print(f"Index '{INDEX_NAME}' created.")


def get_existing_customer_ids(search_client: SearchClient) -> set:
    """Return set of customer_ids currently in the index."""
    results = search_client.search(search_text="*", select=["customer_id"], top=10_000)
    return {r["customer_id"] for r in results}


def upsert_documents(search_client: SearchClient, documents: list, batch_size: int = 1000) -> None:
    total = len(documents)
    for i in range(0, total, batch_size):
        chunk = documents[i : i + batch_size]
        result = search_client.upload_documents(documents=chunk)
        failed = [r for r in result if not r.succeeded]
        if failed:
            for r in failed:
                print(f"  WARN upsert failed for {r.key}: {r.error_message}")
    print(f"Upserted {total:,} document(s) to '{INDEX_NAME}'.")


def delete_stale_documents(search_client: SearchClient, active_ids: set, existing_ids: set) -> None:
    stale = existing_ids - active_ids
    if not stale:
        print("No stale documents to delete.")
        return
    docs = [{"@search.action": "delete", "customer_id": cid} for cid in stale]
    search_client.delete_documents(documents=docs)
    print(f"Deleted {len(stale):,} stale profile(s) from index.")


# ── Key Vault ─────────────────────────────────────────────────────────────────

def get_search_api_key(keyvault_name: str, cred) -> str:
    kv_url = f"https://{keyvault_name}.vault.azure.net"
    client = SecretClient(vault_url=kv_url, credential=cred)
    return client.get_secret(SEARCH_KEY_SECRET).value


# ── Main ──────────────────────────────────────────────────────────────────────

def main(args) -> None:
    cred = _credential(os.environ.get("AZURE_CLIENT_ID"))

    # 1. Read high-risk batch from Blob
    batch_df = read_high_risk_batch(args.storage_account, args.container, cred)
    if batch_df.empty:
        print("Batch CSV is empty — nothing to enrich.")
        return

    customer_ids = batch_df["customer_id"].tolist()

    # 2. Fetch SQL context summaries
    context = fetch_sql_context(args.sql_server, args.sql_db, customer_ids, cred)

    # 3. Get AI Search API key from Key Vault
    api_key = get_search_api_key(args.keyvault_name, cred)

    # 4. Ensure index exists
    ensure_index(args.search_endpoint, api_key)

    search_client = SearchClient(
        endpoint=args.search_endpoint,
        index_name=INDEX_NAME,
        credential=AzureKeyCredential(api_key),
    )

    # 5. Build documents
    print("Building search documents ...")
    documents = []
    for _, row in batch_df.iterrows():
        cid = row["customer_id"]

        # Map feature columns — use 0/None defaults for any missing columns
        def _int(col):
            val = row.get(col)
            return int(val) if pd.notna(val) else 0

        def _float(col):
            val = row.get(col)
            return float(val) if pd.notna(val) else 0.0

        doc = {
            "customer_id":            cid,
            "snapshot_date":          str(row.get("scored_at", ""))[:10],
            "churn_score":            _float("churn_score"),
            "days_since_last_login":  _int("days_since_last_login"),
            "complaints_open":        _int("complaints_open"),
            "competitor_transfer_cnt":_int("competitor_transfer_count"),
            "months_to_rate_reset":   _float("months_to_rate_reset"),
            "segment":                str(row.get("segment", "") or ""),
            "region":                 str(row.get("region", "") or ""),
            "product_summary":     _product_summary(cid,     context["products"]),
            "engagement_summary":  _engagement_summary(cid,  context["engagement"]),
            "complaint_summary":   _complaint_summary(cid,   context["complaints"]),
            "transaction_summary": _transaction_summary(cid, context["transactions"]),
        }
        documents.append(doc)

    # 6. Get current index state and upsert
    existing_ids = get_existing_customer_ids(search_client)
    upsert_documents(search_client, documents)

    # 7. Remove profiles for customers no longer high-risk
    active_ids = set(customer_ids)
    delete_stale_documents(search_client, active_ids, existing_ids)

    print(f"\nEnrichment complete: {len(documents):,} profiles indexed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--storage-account",  dest="storage_account", required=True)
    parser.add_argument("--container",        default=BATCH_CONTAINER)
    parser.add_argument("--sql-server",       dest="sql_server",
                        default=os.environ.get("BANKRETAIN_SQL_SERVER", ""))
    parser.add_argument("--sql-db",           dest="sql_db",
                        default=os.environ.get("BANKRETAIN_SQL_DB", "bankretaindb"))
    parser.add_argument("--keyvault-name",    dest="keyvault_name",   required=True)
    parser.add_argument("--search-endpoint",  dest="search_endpoint", required=True)
    args = parser.parse_args()
    main(args)
