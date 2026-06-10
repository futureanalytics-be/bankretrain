"""
config.py — Bootstrap os.environ from st.secrets for Streamlit Community Cloud.

Streamlit Community Cloud exposes secrets via st.secrets but does NOT inject
them into os.environ automatically. DefaultAzureCredential's EnvironmentCredential
and every os.environ[] read in this app depend on those vars being in the process
environment.

This module copies missing keys from st.secrets → os.environ at import time.
Already-set env vars (local dev via `source sql.env`) are never overwritten.
"""

import os
import streamlit as st

_KEYS = (
    # Azure SQL connection
    "BANKRETAIN_SQL_SERVER",
    "BANKRETAIN_SQL_DB",
    # Azure subscription / AML workspace
    "AZURE_SUBSCRIPTION_ID",
    "AML_WORKSPACE_NAME",
    "ML_RESOURCE_GROUP",
    # Service principal — picked up by DefaultAzureCredential EnvironmentCredential
    "AZURE_CLIENT_ID",
    "AZURE_CLIENT_SECRET",
    "AZURE_TENANT_ID",
)

for _key in _KEYS:
    if _key not in os.environ:
        try:
            _val = st.secrets.get(_key)
            if _val:
                os.environ[_key] = str(_val)
        except Exception:
            pass
