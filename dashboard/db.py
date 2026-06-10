"""
db.py — Azure SQL connection helper for the BankRetain dashboard.

Creates a fresh connection per query to avoid pyodbc "connection busy"
errors when Streamlit runs multiple elements concurrently.
The Entra token is cached so credential round-trips only happen on expiry.
"""

import os
import struct
import time
import streamlit as st
import pyodbc
from azure.identity import DefaultAzureCredential
import config  # noqa: F401 — bootstraps os.environ from st.secrets on Community Cloud


@st.cache_resource(show_spinner=False)
def _credential() -> DefaultAzureCredential:
    return DefaultAzureCredential()


def _connect() -> pyodbc.Connection:
    server   = os.environ["BANKRETAIN_SQL_SERVER"]
    database = os.environ["BANKRETAIN_SQL_DB"]

    token        = _credential().get_token("https://database.windows.net/.default")
    token_bytes  = token.token.encode("UTF-16-LE")
    token_struct = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)

    conn_str = (
        f"Driver={{ODBC Driver 18 for SQL Server}};"
        f"Server={server};"
        f"Database={database};"
        f"Encrypt=yes;"
        f"TrustServerCertificate=no;"
    )
    return pyodbc.connect(conn_str, attrs_before={1256: token_struct}, timeout=60, autocommit=True)


def query(sql: str) -> "pd.DataFrame":
    import pandas as pd

    for attempt in range(1, 8):
        try:
            conn   = _connect()
            cursor = conn.cursor()
            cursor.execute(sql)
            columns = [col[0] for col in cursor.description]
            rows    = cursor.fetchall()
            cursor.close()
            conn.close()
            return pd.DataFrame.from_records(rows, columns=columns)
        except Exception as e:
            msg = str(e)
            if "40613" in msg or "HYT00" in msg:
                st.toast(f"Database resuming… ({attempt}/7)", icon="⏳")
                time.sleep(20)
            else:
                raise
    raise RuntimeError("Could not connect to Azure SQL after 7 attempts")
