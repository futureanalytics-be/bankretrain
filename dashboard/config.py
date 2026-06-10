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

    # Detect Ubuntu version at runtime — Community Cloud has moved between
    # 22.04 (jammy) and 24.04 (noble); hardcoding a version breaks on upgrades.
    _SCRIPT = """
set -e
UBUNTU_VER=$(lsb_release -rs)
UBUNTU_CODENAME=$(lsb_release -cs)
curl -fsSL "https://packages.microsoft.com/config/ubuntu/${UBUNTU_VER}/packages-microsoft-prod.deb" \
    -o /tmp/packages-microsoft-prod.deb
sudo dpkg -i /tmp/packages-microsoft-prod.deb
sudo apt-get update -qq
sudo ACCEPT_EULA=Y DEBIAN_FRONTEND=noninteractive apt-get install -yq msodbcsql18
"""
    result = subprocess.run(
        ["bash", "-c", _SCRIPT],
        timeout=180,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        # Surface the failure so it shows in Streamlit logs
        raise RuntimeError(
            f"ODBC driver install failed (exit {result.returncode}):\n"
            f"{result.stderr[-2000:]}"
        )


# Called lazily from db.py on first connection attempt — not at import time,
# so Streamlit can start serving the UI before the ~90s install completes.
