"""
queue_store.py — Read/write helpers for approved_outreach and compliance_review_queue

Used by dashboard pages 03 and 04. All writes are idempotent on the table
structure (tables are created by the orchestration pipeline on first run).
Auth: Entra token via DefaultAzureCredential (same as dashboard/db.py).
"""

import json
import os
import struct
from datetime import datetime, timezone
from typing import Optional

_UNICODE_MAP = str.maketrans({
    # Unicode smart quotes / dashes
    "\u2018": "'", "\u2019": "'",
    "\u201c": '"', "\u201d": '"',
    "\u2013": "-", "\u2014": "-", "\u2015": "-",
    "\u20ac": "EUR", "\u00a0": " ",
    # Control-char low bytes written before the write-path _sanitize fix
    "\x18": "'",
    "\x19": "'",
    "\x1c": '"',
    "\x1d": '"',
    "\x13": "-",
    "\x14": "-",
    "\x15": "",
})


def _sanitize(text) -> str:
    if not isinstance(text, str):
        return text
    return text.translate(_UNICODE_MAP)

import pandas as pd
import streamlit as st
from azure.identity import DefaultAzureCredential

try:
    import pyodbc
except ImportError:
    pyodbc = None  # allow import in environments without pyodbc


# ── Connection ────────────────────────────────────────────────────────────────

@st.cache_resource(show_spinner=False)
def _credential() -> DefaultAzureCredential:
    return DefaultAzureCredential()


def _connect():
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


# ── Approved outreach ─────────────────────────────────────────────────────────

def get_approved_outreach(batch_date: Optional[str] = None) -> pd.DataFrame:
    """Return approved_outreach rows, optionally filtered by batch_date (YYYY-MM-DD)."""
    conn   = _connect()
    cursor = conn.cursor()
    if batch_date:
        cursor.execute("""
            SELECT customer_id, batch_date, offer_id, channel, churn_reason,
                   confidence, LEFT(message_draft, 500) AS message_preview,
                   agent1_tokens + agent2_tokens + agent3_tokens AS total_tokens,
                   approved_at
            FROM dbo.approved_outreach
            WHERE batch_date = ?
            ORDER BY approved_at DESC
        """, batch_date)
    else:
        cursor.execute("""
            SELECT customer_id, batch_date, offer_id, channel, churn_reason,
                   confidence, LEFT(message_draft, 500) AS message_preview,
                   agent1_tokens + agent2_tokens + agent3_tokens AS total_tokens,
                   approved_at
            FROM dbo.approved_outreach
            ORDER BY approved_at DESC
        """)
    cols = [col[0] for col in cursor.description]
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    df = pd.DataFrame.from_records(rows, columns=cols)
    if "message_preview" in df.columns:
        df["message_preview"] = df["message_preview"].apply(_sanitize)
    return df


def get_approved_message(customer_id: str, batch_date: str) -> Optional[str]:
    """Return the full message_draft for a specific customer+batch."""
    conn   = _connect()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT message_draft FROM dbo.approved_outreach
        WHERE customer_id = ? AND batch_date = ?
    """, customer_id, batch_date)
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return _sanitize(row[0]) if row else None


# ── Compliance review queue ───────────────────────────────────────────────────

def get_review_queue(batch_date: Optional[str] = None,
                     status_filter: Optional[str] = None) -> pd.DataFrame:
    """Return compliance_review_queue rows with optional filters."""
    conn   = _connect()
    cursor = conn.cursor()

    conditions = []
    params: list = []
    if batch_date:
        conditions.append("batch_date = ?")
        params.append(batch_date)
    if status_filter:
        conditions.append("status = ?")
        params.append(status_filter)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    cursor.execute(f"""
        SELECT id, customer_id, batch_date, offer_id, channel, churn_reason,
               LEFT(message_draft, 500) AS message_preview,
               violated_rules, review_notes, status,
               reviewed_by, reviewed_at, created_at
        FROM dbo.compliance_review_queue
        {where}
        ORDER BY created_at DESC
    """, params)
    cols = [col[0] for col in cursor.description]
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return pd.DataFrame.from_records(rows, columns=cols)


def get_queue_message(queue_id: int) -> Optional[dict]:
    """Return the full message and metadata for a queue item by id."""
    conn   = _connect()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, customer_id, batch_date, offer_id, channel, churn_reason,
               message_draft, violated_rules, review_notes, status,
               reviewed_by, reviewed_at
        FROM dbo.compliance_review_queue
        WHERE id = ?
    """, queue_id)
    row = cursor.fetchone()
    cols = [col[0] for col in cursor.description]
    cursor.close()
    conn.close()
    if not row:
        return None
    result = dict(zip(cols, row))
    if result.get("message_draft"):
        result["message_draft"] = _sanitize(result["message_draft"])
    if result.get("review_notes"):
        result["review_notes"] = _sanitize(result["review_notes"])
    if result.get("violated_rules"):
        try:
            result["violated_rules"] = json.loads(result["violated_rules"])
        except (json.JSONDecodeError, TypeError):
            pass
    return result


def update_queue_item(queue_id: int, decision: str, reviewer: str,
                      edited_draft: Optional[str] = None) -> None:
    """
    Record a human review decision on a compliance_review_queue item.

    decision: 'approved' | 'rejected'
    reviewer: identity of the reviewer (e.g. email from Streamlit session)
    edited_draft: if the reviewer edited the message, pass the new text
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
            # Mirror the edited + approved message into approved_outreach
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


# ── Batch summary stats ───────────────────────────────────────────────────────

def get_batch_summary() -> pd.DataFrame:
    """Return a summary table: batch_date, approved_count, review_count, pass_rate."""
    conn   = _connect()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            COALESCE(a.batch_date, r.batch_date) AS batch_date,
            COALESCE(a.approved_count, 0)        AS approved_count,
            COALESCE(r.review_count,  0)         AS review_count,
            CAST(COALESCE(a.approved_count, 0) AS FLOAT) /
                NULLIF(COALESCE(a.approved_count, 0) + COALESCE(r.review_count, 0), 0)
                                                 AS pass_rate
        FROM (
            SELECT batch_date, COUNT(*) AS approved_count
            FROM dbo.approved_outreach GROUP BY batch_date
        ) a
        FULL OUTER JOIN (
            SELECT batch_date, COUNT(*) AS review_count
            FROM dbo.compliance_review_queue GROUP BY batch_date
        ) r ON a.batch_date = r.batch_date
        ORDER BY batch_date DESC
    """)
    cols = [col[0] for col in cursor.description]
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return pd.DataFrame.from_records(rows, columns=cols)
