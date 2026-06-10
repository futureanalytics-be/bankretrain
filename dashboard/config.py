"""
config.py — Bootstrap os.environ from st.secrets for Streamlit Community Cloud,
and install the Microsoft ODBC Driver 18 on Linux if not already present.

Streamlit Community Cloud exposes secrets via st.secrets but does NOT inject
them into os.environ automatically. DefaultAzureCredential's EnvironmentCredential
and every os.environ[] read in this app depend on those vars being in the process
environment.

This module copies missing keys from st.secrets → os.environ at import time.
Already-set env vars (local dev via `source sql.env`) are never overwritten.
"""

import os
import sys
import glob
import subprocess
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

# ── Microsoft ODBC Driver 18 (Linux / Streamlit Community Cloud) ──────────────
# pyodbc requires the MS ODBC Driver at the OS level. On Mac/Windows it is
# installed via brew/installer. On Streamlit Community Cloud (Ubuntu 22.04)
# adminuser has passwordless sudo, so we install on first boot if absent.

def _install_ms_odbc():
    if sys.platform != "linux":
        return
    if glob.glob("/opt/microsoft/msodbcsql18/lib64/libmsodbcsql-18.*.so.*.*"):
        return  # Already installed

    _SCRIPT = """
set -e
curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
    | gpg --dearmor \
    | sudo tee /usr/share/keyrings/microsoft-prod.gpg > /dev/null
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft-prod.gpg] \
https://packages.microsoft.com/ubuntu/22.04/prod jammy main" \
    | sudo tee /etc/apt/sources.list.d/mssql-release.list > /dev/null
sudo apt-get update -qq
sudo ACCEPT_EULA=Y DEBIAN_FRONTEND=noninteractive apt-get install -yq msodbcsql18
"""
    try:
        subprocess.run(
            ["bash", "-c", _SCRIPT],
            check=True, timeout=180,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass  # Connection attempt will surface the error with a clear message


_install_ms_odbc()
