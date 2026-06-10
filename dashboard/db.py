"""
db.py — Azure SQL connection helper for the BankRetain dashboard.

Creates a fresh connection per query to avoid connection-busy errors
when Streamlit runs multiple elements concurrently.
The Entra token is cached so credential round-trips only happen on expiry.

Uses pytds (python-tds) — pure-Python TDS, no system ODBC driver required,
so it works on Streamlit Community Cloud out of the box.
"""

import os
import time
import streamlit as st
import pytds
from azure.identity import DefaultAzureCredential
import config  # noqa: F401 — bootstraps os.environ from st.secrets on Community Cloud


@st.cache_resource(show_spinner=False)
def _credential() -> DefaultAzureCredential:
    return DefaultAzureCredential()


def _connect():
    server   = os.environ["BANKRETAIN_SQL_SERVER"]
    database = os.environ["BANKRETAIN_SQL_DB"]
    token    = _credential().get_token("https://database.windows.net/.default")

    return pytds.connect(
        server,
        database=database,
        access_token=token.token,
        autocommit=True,
    )


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
