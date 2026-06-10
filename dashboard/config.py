"""
config.py — Bootstrap os.environ from st.secrets for Streamlit Community Cloud,
and install the Microsoft ODBC Driver 18 without root via dpkg -x.

Streamlit Community Cloud exposes secrets via st.secrets but does NOT inject
them into os.environ automatically. DefaultAzureCredential's EnvironmentCredential
and every os.environ[] read in this app depend on those vars being in the process
environment.

This module copies missing keys from st.secrets → os.environ at import time.
Already-set env vars (local dev via `source sql.env`) are never overwritten.
"""

import glob
import os
import subprocess
import sys
from pathlib import Path

import streamlit as st

_KEYS = (
    "BANKRETAIN_SQL_SERVER",
    "BANKRETAIN_SQL_DB",
    "AZURE_SUBSCRIPTION_ID",
    "AML_WORKSPACE_NAME",
    "ML_RESOURCE_GROUP",
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
# adminuser has no sudo, so we use `dpkg -x` to extract the .deb into the user's
# home directory (no root required). unixodbc is pre-installed via packages.txt.
# ODBCSYSINI points pyodbc at a custom odbcinst.ini that references the extracted .so.

_INSTALL_DIR = Path.home() / ".msodbcsql18"
_ODBC_CFG    = Path("/tmp/bankretain-odbc")


def _configure_odbc_env(driver_lib: str) -> None:
    _ODBC_CFG.mkdir(parents=True, exist_ok=True)
    (_ODBC_CFG / "odbcinst.ini").write_text(
        "[ODBC Driver 18 for SQL Server]\n"
        "Description=Microsoft ODBC Driver 18 for SQL Server\n"
        f"Driver={driver_lib}\n"
        "UsageCount=1\n"
    )
    (_ODBC_CFG / "odbc.ini").write_text("")
    os.environ.setdefault("ODBCSYSINI", str(_ODBC_CFG))
    os.environ.setdefault("ODBCINI",    str(_ODBC_CFG / "odbc.ini"))


def install_ms_odbc() -> None:
    """Install MS ODBC Driver 18 to ~/.msodbcsql18 without root. No-op if done."""
    if sys.platform != "linux":
        return

    libs = glob.glob(str(_INSTALL_DIR / "opt/microsoft/msodbcsql18/lib64/libmsodbcsql-18.*.so.*.*"))
    if libs:
        _configure_odbc_env(libs[0])
        return

    # Read Ubuntu version from /etc/os-release (lsb_release not available)
    ubuntu_ver = "22.04"
    try:
        with open("/etc/os-release") as f:
            for line in f:
                if line.startswith("VERSION_ID="):
                    ubuntu_ver = line.split("=", 1)[1].strip().strip('"')
                    break
    except Exception:
        pass

    # Try known stable .deb versions; curl exits non-zero on 404 with -f flag
    deb_path = "/tmp/msodbcsql18.deb"
    downloaded = False
    for ver in ["18.4.1.1-1", "18.3.3.1-1", "18.2.1.1-1"]:
        url = (
            f"https://packages.microsoft.com/ubuntu/{ubuntu_ver}/prod"
            f"/pool/main/m/msodbcsql18/msodbcsql18_{ver}_amd64.deb"
        )
        r = subprocess.run(
            ["curl", "-fsSL", "--output", deb_path, url],
            capture_output=True, text=True, timeout=60,
        )
        if r.returncode == 0:
            downloaded = True
            break

    if not downloaded:
        raise RuntimeError(
            f"Could not download msodbcsql18 for Ubuntu {ubuntu_ver}. "
            "Check network access from Streamlit Community Cloud."
        )

    _INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        ["dpkg", "-x", deb_path, str(_INSTALL_DIR)],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(f"dpkg -x failed: {r.stderr}")

    libs = glob.glob(str(_INSTALL_DIR / "opt/microsoft/msodbcsql18/lib64/libmsodbcsql-18.*.so.*.*"))
    if not libs:
        raise RuntimeError("ODBC .so not found after dpkg -x extraction.")

    _configure_odbc_env(libs[0])
