"""
db.py — Azure SQL connection helper for the BankRetain dashboard.

Uses pymssql (bundles FreeTDS, no system ODBC driver required) with an
Azure AD access token — compatible with Streamlit Community Cloud where
sudo is not available to install Microsoft ODBC Driver 18.
"""

import os
import time
import streamlit as st
import pymssql
from azure.identity import DefaultAzureCredential
import config  # noqa: F401 — bootstraps os.environ from st.secrets


@st.cache_resource(show_spinner=False)
def _credential() -> DefaultAzureCredential:
    return DefaultAzureCredential()


def _connect() -> pymssql.Connection:
    server   = os.environ["BANKRETAIN_SQL_SERVER"]
    database = os.environ["BANKRETAIN_SQL_DB"]

    token = _credential().get_token("https://database.windows.net/.default")

    return pymssql.connect(
        server=server,
        database=database,
        access_token=token.token,
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
