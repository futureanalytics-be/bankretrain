"""
seed_sql.py — BankRetain Azure SQL seeder

Loads synthetic data DataFrames into Azure SQL Database.
Creates tables if they do not exist. Truncates before inserting
to allow clean reruns.

Authentication:
  - Development: SQL username + password from environment variables
  - Production: Azure AD managed identity (no password needed)
    Set USE_MANAGED_IDENTITY=true in environment

Environment variables:
  BANKRETAIN_SQL_SERVER       e.g. bankretain-sql.database.windows.net
  BANKRETAIN_SQL_DB           e.g. bankretain-db
  BANKRETAIN_SQL_USER         (dev only)
  BANKRETAIN_SQL_PASSWORD     (dev only)
  USE_MANAGED_IDENTITY        true | false (default: false)
"""

import logging
import os
import struct
from typing import Dict

import pandas as pd
import pyodbc
from azure.identity import DefaultAzureCredential

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# DDL — table creation statements
# These must match the Azure SQL schema provisioned via Bicep.
# ─────────────────────────────────────────────────────────────────────────────

DDL = {
    "customers": """
        IF NOT EXISTS (
            SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[customers]')
            AND type = N'U'
        )
        CREATE TABLE dbo.customers (
            customer_id             NVARCHAR(10)  NOT NULL PRIMARY KEY,
            snapshot_date           DATE          NOT NULL,
            age                     INT,
            region                  NVARCHAR(50),
            segment                 NVARCHAR(30),
            customer_since_date     DATE,
            preferred_language      NVARCHAR(5),
            salary_account_flag     BIT,
            relationship_manager_id NVARCHAR(10),
            churned                 BIT,
            churn_signal_count      INT,
            signal_salary_stop          BIT,
            signal_app_inactive         BIT,
            signal_product_reduction    BIT,
            signal_competitor_transfers BIT
        )
    """,

    "products": """
        IF NOT EXISTS (
            SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[products]')
            AND type = N'U'
        )
        CREATE TABLE dbo.products (
            product_id   NVARCHAR(10)  NOT NULL PRIMARY KEY,
            product_type NVARCHAR(50),
            product_name NVARCHAR(100)
        )
    """,

    "customer_products": """
        IF NOT EXISTS (
            SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[customer_products]')
            AND type = N'U'
        )
        CREATE TABLE dbo.customer_products (
            id                   INT IDENTITY(1,1) PRIMARY KEY,
            customer_id          NVARCHAR(10),
            product_id           NVARCHAR(10),
            start_date           DATE,
            end_date             DATE,
            status               NVARCHAR(20),
            fixed_rate_end_date  DATE
        )
    """,

    "transactions": """
        IF NOT EXISTS (
            SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[transactions]')
            AND type = N'U'
        )
        CREATE TABLE dbo.transactions (
            transaction_id           NVARCHAR(15) NOT NULL PRIMARY KEY,
            customer_id              NVARCHAR(10),
            transaction_date         DATE,
            amount_eur               DECIMAL(12,2),
            direction                NVARCHAR(10),
            merchant_category        NVARCHAR(50),
            counterparty_iban        NVARCHAR(34),
            counterparty_bank_bic    NVARCHAR(11),
            channel                  NVARCHAR(20),
            is_competitor_transfer   BIT
        )
    """,

    "complaints": """
        IF NOT EXISTS (
            SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[complaints]')
            AND type = N'U'
        )
        CREATE TABLE dbo.complaints (
            complaint_id     NVARCHAR(12) NOT NULL PRIMARY KEY,
            customer_id      NVARCHAR(10),
            opened_date      DATE,
            closed_date      DATE,
            category         NVARCHAR(50),
            status           NVARCHAR(20),
            resolution_days  INT
        )
    """,

    "nps_responses": """
        IF NOT EXISTS (
            SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[nps_responses]')
            AND type = N'U'
        )
        CREATE TABLE dbo.nps_responses (
            id            INT IDENTITY(1,1) PRIMARY KEY,
            customer_id   NVARCHAR(10),
            response_date DATE,
            score         INT,
            verbatim_text NVARCHAR(500)
        )
    """,

    "app_sessions": """
        IF NOT EXISTS (
            SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[app_sessions]')
            AND type = N'U'
        )
        CREATE TABLE dbo.app_sessions (
            id                         INT IDENTITY(1,1) PRIMARY KEY,
            customer_id                NVARCHAR(10),
            session_date               DATE,
            session_duration_seconds   INT,
            feature_used               NVARCHAR(50)
        )
    """,

    "branch_visits": """
        IF NOT EXISTS (
            SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[branch_visits]')
            AND type = N'U'
        )
        CREATE TABLE dbo.branch_visits (
            id           INT IDENTITY(1,1) PRIMARY KEY,
            customer_id  NVARCHAR(10),
            visit_date   DATE,
            branch_id    NVARCHAR(10),
            purpose      NVARCHAR(50)
        )
    """,
}

# Load order matters — foreign key-like dependencies
TABLE_ORDER = [
    "customers",
    "products",
    "customer_products",
    "transactions",
    "complaints",
    "nps_responses",
    "app_sessions",
    "branch_visits",
]

# Chunk size for bulk inserts — keeps memory manageable for 50k customers
CHUNK_SIZE = 2_000


def seed_database(data: Dict[str, pd.DataFrame], population: str = "a") -> None:
    """
    Seed all tables into Azure SQL.

    Population A is the primary training dataset and is loaded
    into the live tables. Population B is kept locally and loaded
    only when simulating the drift retraining scenario.
    """
    conn = _get_connection()
    cursor = conn.cursor()

    log.info(f"Connected to Azure SQL. Seeding Population {population.upper()}...")

    # Create tables if they do not exist
    for table_name in TABLE_ORDER:
        if table_name in DDL:
            log.info(f"  Ensuring table exists: {table_name}")
            cursor.execute(DDL[table_name])
    conn.commit()

    # For Population A: truncate and reload (clean baseline)
    # For Population B: append only (simulating new data arriving)
    if population == "a":
        log.info("Truncating existing tables for Population A clean load...")
        for table_name in reversed(TABLE_ORDER):
            cursor.execute(f"DELETE FROM dbo.{table_name}")
        conn.commit()

    # Insert each table
    for table_name in TABLE_ORDER:
        if table_name not in data:
            log.warning(f"  No data for table {table_name} — skipping")
            continue

        df = data[table_name].copy()
        df = _clean_dataframe(df)

        row_count = len(df)
        log.info(f"  Inserting {row_count:,} rows into {table_name}...")

        _bulk_insert(cursor, conn, table_name, df)
        log.info(f"  ✓ {table_name} done")

    cursor.close()
    conn.close()
    log.info("Seeding complete.")


def _bulk_insert(cursor, conn, table_name: str, df: pd.DataFrame) -> None:
    """Insert DataFrame into SQL table in chunks using executemany."""
    cursor.fast_executemany = True
    columns = list(df.columns)
    placeholders = ", ".join(["?" for _ in columns])
    col_list = ", ".join([f"[{c}]" for c in columns])
    sql = f"INSERT INTO dbo.{table_name} ({col_list}) VALUES ({placeholders})"

    for start in range(0, len(df), CHUNK_SIZE):
        chunk = df.iloc[start : start + CHUNK_SIZE]
        rows  = [tuple(row) for row in chunk.itertuples(index=False, name=None)]
        cursor.executemany(sql, rows)
        conn.commit()


def _clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepare DataFrame for SQL insertion.
    - Convert date objects to strings (pyodbc handles these cleanly)
    - Replace NaN with None (SQL NULL)
    - Convert numpy booleans to Python booleans
    """
    df = df.copy()

    for col in df.columns:
        # Convert date columns
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.date

        # Convert numpy bool to Python bool
        if df[col].dtype == bool or str(df[col].dtype) == "bool":
            df[col] = df[col].astype(object)

    # Replace NaN / NaT with None
    df = df.where(pd.notnull(df), None)

    return df


def _get_connection(max_attempts: int = 8, retry_delay: int = 20) -> pyodbc.Connection:
    """
    Return an authenticated pyodbc connection to Azure SQL.

    Retries on login timeout and database-unavailable (40613) errors,
    which occur when the serverless database has auto-paused.
    """
    server   = os.environ["BANKRETAIN_SQL_SERVER"]
    database = os.environ["BANKRETAIN_SQL_DB"]
    use_mi   = os.environ.get("USE_MANAGED_IDENTITY", "false").lower() == "true"

    for attempt in range(1, max_attempts + 1):
        try:
            if use_mi:
                credential   = DefaultAzureCredential()
                token        = credential.get_token("https://database.windows.net/.default")
                token_bytes  = token.token.encode("UTF-16-LE")
                token_struct = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)
                conn_str = (
                    f"Driver={{ODBC Driver 18 for SQL Server}};"
                    f"Server={server};"
                    f"Database={database};"
                    f"Encrypt=yes;"
                    f"TrustServerCertificate=no;"
                )
                return pyodbc.connect(conn_str, attrs_before={1256: token_struct}, timeout=60)
            else:
                conn_str = (
                    f"Driver={{ODBC Driver 18 for SQL Server}};"
                    f"Server={server};"
                    f"Database={database};"
                    f"UID={os.environ['BANKRETAIN_SQL_USER']};"
                    f"PWD={os.environ['BANKRETAIN_SQL_PASSWORD']};"
                    f"Encrypt=yes;"
                    f"TrustServerCertificate=no;"
                )
                return pyodbc.connect(conn_str, timeout=60)

        except Exception as e:
            msg = str(e)
            if "40613" in msg or "HYT00" in msg or "08S01" in msg:
                log.info(f"Database resuming (attempt {attempt}/{max_attempts}), retrying in {retry_delay}s...")
                import time
                time.sleep(retry_delay)
            else:
                raise

    raise RuntimeError(f"Could not connect to {server}/{database} after {max_attempts} attempts")
