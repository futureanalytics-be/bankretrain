"""
queue_store.py — Read/write helpers for approved_outreach and compliance_review_queue

Reads come from Azure Blob Storage (Parquet cache) — no ODBC driver needed.
Writes (human review decisions) go directly to Azure SQL via pyodbc + MS ODBC
Driver 18 (installed lazily via dpkg -x without root on Streamlit Community Cloud).
"""

import os
import struct
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import streamlit as st
from azure.identity import DefaultAzureCredential

from blob_store import (  # noqa — all reads come from blob cache
    get_approved_message,
    get_approved_outreach,
    get_batch_summary,
    get_queue_message,
    get_review_queue,
)

try:
    import pyodbc
except ImportError:
    pyodbc = None


# Re-export read helpers so existing page imports still work unchanged
__all__ = [
    "get_approved_outreach",
    "get_approved_message",
    "get_review_queue",
    "get_queue_message",
    "get_batch_summary",
    "update_queue_item",
]


# ── SQL write-back (human review decisions only) ──────────────────────────────

@st.cache_resource(show_spinner=False)
def _credential() -> DefaultAzureCredential:
    return DefaultAzureCredential()


def _connect():
    from config import install_ms_odbc
    install_ms_odbc()  # dpkg -x, no-op if already done

    cred     = _credential()
    server   = os.environ["BANKRETAIN_SQL_SERVER"]
    database = os.environ["BANKRETAIN_SQL_DB"]

    token        = cred.get_token("https://database.windows.net/.default")
    token_bytes  = token.token.encode("UTF-16-LE")
    token_struct = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)

    conn_str = (
        f"Driver={{ODBC Driver 18 for SQL Server}};"
        f"Server={server};Database={database};"
        f"Encrypt=yes;TrustServerCertificate=no;"
    )
    return pyodbc.connect(conn_str, attrs_before={1256: token_struct},
                          timeout=60, autocommit=True)


def update_queue_item(queue_id: int, decision: str, reviewer: str,
                      edited_draft: Optional[str] = None) -> None:
    """
    Record a human review decision on a compliance_review_queue item.

    decision: 'approved' | 'rejected'
    reviewer: identity of the reviewer
    edited_draft: pass the new text if the reviewer edited the message
    """
    conn   = _connect()
    cursor = conn.cursor()

    reviewed_at = datetime.now(timezone.utc).isoformat()
    new_status  = "approved" if decision == "approved" else "rejected"

    if edited_draft:
        cursor.execute("""
            UPDATE dbo.compliance_review_queue
            SET status = ?, reviewed_by = ?, reviewed_at = ?, message_draft = ?
            WHERE id = ?
        """, new_status, reviewer, reviewed_at, edited_draft, queue_id)

        if decision == "approved":
            cursor.execute("""
                SELECT customer_id, batch_date, offer_id, channel, churn_reason
                FROM dbo.compliance_review_queue WHERE id = ?
            """, queue_id)
            r = cursor.fetchone()
            if r:
                cursor.execute("""
                    INSERT INTO dbo.approved_outreach
                        (customer_id, batch_date, offer_id, channel, churn_reason,
                         message_draft, agent1_tokens, agent2_tokens, agent3_tokens)
                    VALUES (?, ?, ?, ?, ?, ?, 0, 0, 0)
                """, r[0], r[1], r[2], r[3], r[4], edited_draft)
    else:
        cursor.execute("""
            UPDATE dbo.compliance_review_queue
            SET status = ?, reviewed_by = ?, reviewed_at = ?
            WHERE id = ?
        """, new_status, reviewer, reviewed_at, queue_id)

    cursor.close()
    conn.close()
