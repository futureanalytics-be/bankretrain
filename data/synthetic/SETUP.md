# Synthetic Data Generation — Setup and Run Instructions

## Phase 1.4 — BankRetain Project

---

## Files in This Folder

```text
data/synthetic/
├── generate.py         Entry point — orchestrates the other four scripts
├── population_a.py     Spring/summer baseline data (~10% churn, 50k customers)
├── population_b.py     Autumn/winter drift data (~14% churn, 50k customers)
├── label_generator.py  60-day forward window churn labelling
├── seed_sql.py         Azure SQL connection and bulk insert
└── output/             Parquet files written here after each run (git-ignored)
```

---

## What You Need Installed Locally

Install Python packages:

```bash
pip install pandas numpy pyodbc azure-identity pyarrow
```

Install **ODBC Driver 18 for SQL Server** at the system level (not a Python package):

- **Mac:** `brew install msodbcsql18`
- **Windows/Linux:** search "Download ODBC Driver for SQL Server Microsoft"

---

## Authentication

The Azure SQL server uses **Entra-only authentication** — no SQL username or password exists.

Locally, the scripts authenticate via your active Azure CLI session using `DefaultAzureCredential`, which automatically falls back to `AzureCliCredential`.

**Before running, ensure you are logged in:**

```bash
az login
az account set --subscription 45a3c784-5e35-4769-b4ca-c9f373474aeb
```

Create a `sql.env` file at the repo root (it is gitignored — never commit it):

```bash
export BANKRETAIN_SQL_SERVER="<your-sql-server>.database.windows.net"
export BANKRETAIN_SQL_DB="bankretaindb"
export USE_MANAGED_IDENTITY="true"
```

Then source it before running:

```bash
source sql.env
```

No SQL username or password is needed or accepted. `USE_MANAGED_IDENTITY=true` tells the script to use the Entra token path.

---

## Firewall Note

Your local machine IP must be whitelisted in the SQL server firewall. This was added once via:

```bash
az sql server firewall-rule create \
  --resource-group bankretain-ml-rg \
  --server bankretain-sql-dev-mqi4i4pjzxcdc \
  --name "developer-local" \
  --start-ip-address <your-ip> \
  --end-ip-address <your-ip>
```

If you get a firewall error (40615), your IP has changed. Re-run the command with your current IP from `curl ifconfig.me`.

---

## Run Order

### Step 1 — Generate and seed Population A

From the `data/synthetic/` folder:

```bash
cd data/synthetic

BANKRETAIN_SQL_SERVER="bankretain-sql-dev-mqi4i4pjzxcdc.database.windows.net" \
BANKRETAIN_SQL_DB="bankretaindb" \
USE_MANAGED_IDENTITY="true" \
python generate.py --population a --seed-sql
```

Expected duration: 5–10 minutes.

Expected output:

```text
Generating Population A...
Computing churn labels from 60-day forward window...
Population A churn rate: ~10.0%
Wrote 50,000 rows → population_a_customers.parquet
...
Seeding Population A into Azure SQL...
Population A seeded successfully.
Done.
```

---

### Step 2 — Verify the data landed

Go to **Azure portal → SQL database → Query Editor** and run:

```sql
-- Customer count and churn rate
SELECT
    COUNT(*)                        AS total_customers,
    SUM(CAST(churned AS INT))       AS churned_count,
    AVG(CAST(churned AS FLOAT))     AS churn_rate
FROM dbo.customers;
-- Expected: ~50,000 rows, ~10% churn rate

-- Row counts across all tables
SELECT 'customers'         AS tbl, COUNT(*) AS rows FROM dbo.customers       UNION ALL
SELECT 'transactions'      AS tbl, COUNT(*) AS rows FROM dbo.transactions     UNION ALL
SELECT 'complaints'        AS tbl, COUNT(*) AS rows FROM dbo.complaints       UNION ALL
SELECT 'nps_responses'     AS tbl, COUNT(*) AS rows FROM dbo.nps_responses    UNION ALL
SELECT 'app_sessions'      AS tbl, COUNT(*) AS rows FROM dbo.app_sessions     UNION ALL
SELECT 'branch_visits'     AS tbl, COUNT(*) AS rows FROM dbo.branch_visits    UNION ALL
SELECT 'customer_products' AS tbl, COUNT(*) AS rows FROM dbo.customer_products;

-- Churn label columns present and populated
SELECT TOP 5
    customer_id, churned, churn_signal_count,
    signal_salary_stop, signal_app_inactive,
    signal_product_reduction, signal_competitor_transfers
FROM dbo.customers;
```

---

### Step 3 — Generate Population B locally (do not seed yet)

```bash
BANKRETAIN_SQL_SERVER="bankretain-sql-dev-mqi4i4pjzxcdc.database.windows.net" \
BANKRETAIN_SQL_DB="bankretaindb" \
USE_MANAGED_IDENTITY="true" \
python generate.py --population b
```

No `--seed-sql`. Parquet files land in `output/`. Population B is loaded into Azure SQL only during the Phase 2 drift simulation.

---

## What Happens to the Data After This

```text
Azure SQL (Population A)
        │
        ▼
Feature engineering pipeline (Phase 2)
        └── SQL → derived features → Azure ML managed feature store
```

Azure SQL is the source of truth. Downstream pipelines only read from it. You write to SQL again only in:

- **Phase 2** — seeding Population B to trigger drift retraining
- **Phase 4** — agent pipeline writes approved outreach and compliance queue decisions back to SQL

---

## If `churned` Is Missing or All Null

The label generator writes churn labels back onto the customers table. If `churned` is missing, rerun:

```bash
python generate.py --population a --seed-sql
```

This truncates and reloads Population A cleanly.
