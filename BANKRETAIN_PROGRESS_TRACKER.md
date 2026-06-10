# BankRetain — Build Progress Tracker

**Customer Churn Predictor & Retention Campaign Orchestrator**
*AI-103 & AI-300 Portfolio Project*

Update this file as you complete each task. Replace `[ ]` with `[x]` when done.

> **Adaptation notes** are inline where the original design was changed during build.
> See also: [README.md](README.md) for the full architectural decision log.

---

## Progress Summary

| Phase | Status | Done When |
| --- | --- | --- |
| Phase 1 — Infrastructure and Data | ✅ Complete | Both RGs provisioned, Population A in SQL, dashboard showing data |
| Phase 2 — ML Model and Monitoring | ✅ Complete | Model v1 deployed, batch scoring running, drift monitor configured |
| Phase 3 — Enrichment and Knowledge Stores | ✅ Complete | AI Search populated, content loaded inline (see adaptation note), 30 reference outputs written |
| Phase 4 — Agent Pipeline | ✅ Complete | Three agents working end to end, review queue live in dashboard |
| Phase 5 — Integration and Final Validation | 🔄 In Progress | Full weekly cycle runs, drift simulation complete, all 5 dashboard pages live |

> Update the Status column as you go: ⬜ Not Started → 🔄 In Progress → ✅ Complete

---

## Phase 1 — Infrastructure and Data

**Target duration:** 1 week
**Goal:** Everything provisioned, synthetic data in Azure SQL, minimal dashboard running

### 1.1 Bicep — ML Resource Group (`bankretain-ml-rg`)

- [x] Azure SQL Database (Basic tier)
- [x] SQL schema created: `customers`, `products`, `customer_products`, `transactions`, `complaints`, `nps_responses`, `app_sessions`, `branch_visits`
- [x] Azure ML workspace with system-assigned managed identity enabled
- [x] Application Insights attached to Azure ML workspace
- [x] Azure ML managed feature store
- [x] Storage Account (Azure ML default storage)
- [x] User-assigned managed identity for feature pipeline compute
- [x] Key Vault with SQL connection string secret
- [x] All RBAC assignments for ML layer deployed as code

### 1.2 Bicep — AI Resource Group (`bankretain-ai-rg`)

- [x] Azure AI Foundry hub
- [x] Azure AI Foundry project (`bankretain-agents-dev`) with system-assigned managed identity
- [x] Azure AI Search (Free tier for dev / Basic for prod)
- [x] Customer profile index schema deployed:
  - [x] `customer_id` (filterable, retrievable)
  - [x] `snapshot_date` (filterable)
  - [x] `churn_score` (filterable)
  - [x] `days_since_last_login` (filterable)
  - [x] `complaints_open` (filterable)
  - [x] `competitor_transfer_count` (filterable)
  - [x] `months_to_rate_reset` (filterable)
  - [x] `segment` (filterable)
  - [x] `region` (filterable)
  - [x] `product_summary` (searchable, retrievable)
  - [x] `engagement_summary` (searchable, retrievable)
  - [x] `complaint_summary` (searchable, retrievable)
  - [x] `transaction_summary` (searchable, retrievable)
- [x] Azure AI Services account (`bankretain-ai-svc-dev-jrkvoy`, `germanywestcentral`)
  - [x] `gpt-oss-120b` deployment (GlobalStandard, 10K TPM) — see adaptation note below
  - [x] `text-embedding-3-large` deployment (Standard, 120K TPM) — enables Foundry memory
- [x] Key Vault (Foundry secrets)
- [x] All RBAC assignments for AI layer deployed as code

> **Adaptation — region and model:** The Azure subscription policy restricts deployments to 5 regions
> (`spaincentral`, `uaenorth`, `italynorth`, `germanywestcentral`, `switzerlandnorth`). None of these
> had OpenAI.GlobalStandard quota for `gpt-4.1` or `gpt-4o-mini`. `gpt-oss-120b` (format `OpenAI-OSS`)
> is available via the AIServices quota pool (5000K TPM) in `germanywestcentral` and was used instead.
> The model supports the chat completions API and structured JSON output identically to gpt-4.1.

### 1.3 GitHub Actions — Infrastructure Pipeline

- [x] `deploy-infra.yml` workflow created
- [x] Triggers on push to `infra/` folder
- [x] Authenticates via GitHub Actions SP (OIDC — no stored client secret)
- [x] Deploys `ml-rg/main.bicep` first, then `ai-rg/main.bicep`
- [x] Resource IDs output to GitHub Actions environment variables

### 1.4 Synthetic Data Generation

- [x] Files placed in `data/synthetic/` folder
- [x] Python packages installed (`pandas`, `numpy`, `pyodbc`, `azure-identity`, `pyarrow`)
- [x] ODBC Driver 18 for SQL Server installed (local dev machine only)
- [x] Environment variables set (`BANKRETAIN_SQL_SERVER`, `BANKRETAIN_SQL_DB`, `USE_MANAGED_IDENTITY` — saved in gitignored `sql.env`)
- [x] `generate.py --population a --seed-sql` run successfully
- [x] Azure SQL verified: ~50,000 rows in `customers`, churn rate 9.3%
- [x] Azure SQL verified: `churned` column present and populated on `customers` table
- [x] Azure SQL verified: all 8 tables have rows
- [x] `generate.py --population b` run (no seed — saved locally as parquet)
- [x] Population B parquet files saved in `data/synthetic/output/`

### 1.5 Minimal Streamlit Dashboard (Phase 1 scope)

- [x] `dashboard/app.py` created
- [x] `dashboard/pages/01_data_overview.py` created
  - [x] Customer count by segment and region
  - [x] Product distribution chart
  - [x] Churn rate by segment (Population A)
  - [x] Key feature distributions (`days_since_last_login`, `competitor_transfer_count`, `complaints_open`)
- [x] Dashboard running locally against Azure SQL
- [x] Dashboard deployed to Streamlit Community Cloud (bankretain.streamlit.app)

> **Adaptation — dashboard reads:** Dashboard originally read from Azure SQL via pyodbc. Streamlit
> Community Cloud runs as a non-root user with no access to apt; Microsoft ODBC Driver 18 cannot be
> installed. All page-load reads migrated to Azure Blob Storage Parquet cache (`dashboard-cache`
> container). Only the page 04 human review write-back still uses pyodbc, with the driver extracted
> via `dpkg -x` (no root needed). See `dashboard/blob_store.py` and `dashboard/config.py`.

**✅ Phase 1 done when:** Both resource groups provisioned via Bicep CI/CD ✓, Population A in Azure SQL ✓, dashboard deployed and showing data ✓.

---

## Phase 2 — ML Model and Monitoring

**Target duration:** 1 week
**Goal:** Trained model v1 deployed, monitoring configured, retraining pipeline ready

### 2.1 Feature Engineering Pipeline

- [x] `ml/features/feature_set.py` — feature definitions in Azure ML managed feature store
  - [x] `days_since_last_login`
  - [x] `competitor_transfer_count` (last 90 days)
  - [x] `complaints_open`
  - [x] `months_to_rate_reset`
  - [x] `avg_monthly_inflow_eur`
  - [x] `app_logins_last_30d`
  - [x] `app_logins_last_90d`
  - [x] `salary_account_flag`
  - [x] `product_count`
  - [x] `nps_score_last`
- [x] `ml/features/feature_pipeline.py` — Azure ML pipeline: SQL → feature store
  - [x] Runs on serverless compute (Standard_DS3_v2)
  - [ ] Scheduled weekly (Sunday night) — not yet configured as recurring schedule
  - [x] Uses feature pipeline compute MI for SQL access
  - [x] Feature pipeline run tested manually at least once

### 2.2 Model Training — v1 (Population A)

- [x] `ml/training/train.py` — gradient boosting binary classifier (LightGBM)
  - [x] Reads feature store snapshot tagged `dataset_version=population_a`
  - [x] 80/20 train/test split
  - [x] Full MLflow logging schema implemented:
    - [x] Parameters: `model_type`, `n_estimators`, `max_depth`, `learning_rate`, `dataset_version`, `churn_threshold`, `feature_set_version`
    - [x] Metrics: `precision`, `recall`, `f1`, `auc`, `false_positive_rate`
    - [x] Artifacts: `confusion_matrix.png`, `feature_importance.png`
- [x] `ml/training/pipeline.py` — Azure ML training pipeline definition
  - [x] Runs on serverless compute (Standard_DS3_v2)
  - [x] Outputs registered model to model registry with `status = staging`
- [x] Model v1 registered in Azure ML model registry

### 2.3 Model Evaluation and Deployment

- [x] `ml/training/evaluate.py` — evaluation script
  - [x] Computes all metrics against held-out test set
  - [x] Fails pipeline if precision < 0.75
- [x] Online endpoint deployed via Bicep (not manual portal)
  - [x] `ml/scoring/score.py` scoring script written
  - [ ] Canary deployment structure in place (v1 = 100% traffic initially)
- [x] `ml/scoring/batch_score.py` — weekly batch scoring job
  - [x] Reads all 50,000 customers from feature store
  - [x] Applies `churn_threshold = 0.70`
  - [x] Writes `high_risk_batch.csv` to Blob Storage
  - [x] Batch score job tested manually — `high_risk_batch.csv` produced (~800 rows)

### 2.4 Model Monitoring

- [x] `ml/monitoring/drift_monitor.py` — Azure ML Model Monitor configured
  - [x] Data drift signal: feature distribution vs Population A baseline
  - [x] Model performance signal: precision, recall, F1 vs validation baseline
  - [x] Alert threshold: precision drop below 0.72
- [x] `ml/monitoring/alerts.py` — Event Grid topic subscription configured
  - [x] On drift alert: triggers `retrain.yml` GitHub Actions workflow
- [x] `.github/workflows/retrain.yml` — retraining pipeline written
  - [x] Seeds Population B data into Azure SQL
  - [x] Runs feature pipeline on new data
  - [x] Runs training pipeline with `dataset_version=population_b`
  - [x] Registers v2 as staging
  - [x] Initiates canary deployment: v2 10% / v1 90%
  - [x] Notifies model owner for approval

### 2.5 Human Approval Gate

- [x] `ml/registry/promote.py` — model promotion script written
  - [x] Updates model registry tag: staging → production
  - [x] Updates canary split to v2 100% / v1 0%
- [x] Promotion tested manually: v2 promoted to production in model registry

### 2.6 Dashboard Extension (Phase 2 scope)

- [x] `dashboard/pages/02_ml_monitoring.py` created
  - [x] MLflow experiment run history (precision, recall, F1, AUC per run)
  - [x] Current model version in production
  - [x] Drift signal status (green / amber / red)
  - [x] Canary split view if active (v1 vs v2 metric comparison)

**✅ Phase 2 done when:** Model v1 trained and deployed ✓, batch scoring producing `high_risk_batch.csv` ✓, drift monitor configured ✓, retraining pipeline written ✓.

---

## Phase 3 — Enrichment Pipeline and Knowledge Stores

**Target duration:** 3–4 days
**Goal:** Azure AI Search populated weekly, product catalogue and compliance docs available to agents

### 3.1 Enrichment Pipeline

- [x] `ml/scoring/enrichment.py` written
  - [x] Reads `high_risk_batch.csv` from Blob Storage
  - [x] For each high-risk customer, queries Azure SQL for:
    - [x] Last 90 days transactions → `transaction_summary`
    - [x] Open complaints → `complaint_summary`
    - [x] Active products → `product_summary`
    - [x] App sessions last 60 days → `engagement_summary`
  - [x] Upserts profile document to Azure AI Search (`customer_id` as key)
  - [x] Deletes profiles for customers no longer in high-risk batch
  - [x] Writes `churn_score` from batch scoring into the profile document
- [x] `ml/scoring/submit_enrichment.py` written (AML job + Sunday 01:00 UTC schedule)
- [x] Key Vault secret `search-admin-key` populated (one-time manual step)
- [x] Enrichment pipeline tested: 61 high-risk customers indexed successfully
- [x] Azure AI Search index verified: profile documents present and retrievable by `customer_id`

### 3.2 Product Catalogue Content

- [x] `data/product_catalogue/products.md` written
  - [x] 25 synthetic Belgian retail banking retention offers (PR-001 – PR-025)
  - [x] Each offer includes: `product_id`, `product_name`, `product_type`, `target_segment`, `eligibility_rules`, `offer_description`, `retention_use_case`, `channel_fit`
  - [x] Coverage: price_sensitivity (8), service_dissatisfaction (6), product_lifecycle (6), inactivity (5)
- [x] `agents/vector_stores/upload_products.py` written (kept for reference)
- [x] Product catalogue injected inline into Agent 2 system prompt — see adaptation note

### 3.3 Compliance Rules Content

- [x] `data/compliance_rules/rules.md` written
  - [x] Each rule includes: `rule_id`, `category`, `severity`, `rule_text`
  - [x] Coverage:
    - [x] 6 brand tone rules (BT-001–BT-006)
    - [x] 5 FSMA-style regulatory rules (FSMA-001–FSMA-005)
    - [x] 3 MiFID II-style product claim rules (MIFID-001–MIFID-003)
    - [x] 3 personalisation requirements (PERS-001–PERS-003)
    - [x] 4 channel-specific rules (CH-001–CH-004)
- [x] `agents/vector_stores/upload_compliance.py` written (kept for reference)
- [x] Compliance rules injected inline into Agent 3 system prompt — see adaptation note

> **Adaptation — file_search replaced by inline content:** `gpt-oss-120b` uses format `OpenAI-OSS`
> and does not support the `file_search` tool. Products.md (~18 KB) and rules.md (~13 KB) are small
> enough to fit in a single context window and are injected directly into the agent system prompts
> in `pipeline.py`. `upload_products.py` and `upload_compliance.py` are kept in the repo in case
> a future OpenAI-format model with file_search support is deployed.

### 3.4 Reference Evaluation Outputs

- [x] `agents/evaluation/reference_outputs/` folder created
- [x] 30 manually written example good outreach messages
  - [x] Coverage: each churn reason (4) × each channel (2) = 8 base combinations
  - [x] Multiple customer segments represented (standard, starter, student, private_banking)
  - [x] Mix of email and call script formats
  - [x] All 30 pass compliance check: no BT-004 violations, CH-001/CH-002 present, FSMA-002 on investment offers

**✅ Phase 3 done when:** AI Search index populated ✓, product catalogue and compliance rules available to agents (inline) ✓, 30 reference outputs written ✓.

---

## Phase 4 — Agent Pipeline

**Target duration:** 1 week
**Goal:** Three agents working end to end, compliance review queue live in dashboard

### 4.1 Agent System Prompts

- [x] `agents/prompts/agent1_system.md` written
  - [x] Outputs structured JSON: `{customer_id, churn_score, churn_reason, confidence, supporting_signals}`
  - [x] Classifies into exactly one of: `price_sensitivity`, `service_dissatisfaction`, `product_lifecycle`, `inactivity`, `unknown`
  - [x] Sets confidence: `high` / `medium` / `low`
  - [x] Falls back to `unknown` if fewer than 2 clear signals
- [x] `agents/prompts/agent2_system.md` written
  - [x] Reads inline product catalogue (appended to system prompt)
  - [x] Checks customer eligibility before selecting offer
  - [x] Routes to `email` or `call` based on `channel_fit`
  - [x] References at least one specific customer signal in message
  - [x] Output: `{customer_id, offer_id, channel, message_draft, rationale}`
- [x] `agents/prompts/agent3_system.md` written
  - [x] Reads inline compliance rules (appended to system prompt)
  - [x] Any `hard_block` rule failure = immediate `fail` status
  - [x] `flag_for_review` rules flagged but message passes if no hard blocks
  - [x] Output: `{status: pass|fail, violated_rules: [], message_draft, review_notes}`

### 4.2 Azure AI Search Tool for Agent 1

- [x] `agents/tools/search_tool.py` written
  - [x] Tool name: `get_customer_profile`
  - [x] Parameter: `customer_id` (string)
  - [x] Filter: `customer_id eq '{customer_id}'`
  - [x] Returns full profile document for that customer
  - [x] API key retrieved from Key Vault via MI (no hardcoded keys)
- [x] `agents/tools/schemas.py` written — JSON schemas for Agent 1→2→3 contracts
- [x] Tool tested: returns correct profile for a given `customer_id`

### 4.3 Sequential Orchestration

- [x] `agents/orchestration/pipeline.py` written
  - [x] Reads `high_risk_batch.csv` from Blob Storage
  - [x] For each customer: Agent 1 → validate JSON → Agent 2 → Agent 3 → route output
  - [x] Pass → writes to `approved_outreach` table
  - [x] Fail → writes to `compliance_review_queue` table
  - [x] Token counts per agent logged per row
  - [x] Errors handled gracefully (log and skip, do not crash pipeline)
  - [x] `--batch-size N` flag for test runs
  - [x] `_cache_to_blob()` called at end of run — writes 5 Parquet files to `dashboard-cache` container
- [x] Pipeline tested on a batch of 20 customers end to end
- [x] All three agents returning valid structured JSON

### 4.4 State Store for Dashboard Write-back

- [x] `dashboard/state/queue_store.py` written
  - [x] All reads delegated to `blob_store.py` (Parquet cache, no ODBC on page load)
  - [x] `update_queue_item` — human review decision write-back directly to Azure SQL via pyodbc
  - [x] Human review decision writes back to queue and mirrors approved messages to outreach table
- [x] `dashboard/blob_store.py` written
  - [x] `get_customers()` — customers.parquet (segment, region, churned, churn_signal_count)
  - [x] `get_approved_outreach()` — approved_outreach.parquet
  - [x] `get_approved_message()` — single message lookup
  - [x] `get_review_queue()` — compliance_review_queue.parquet
  - [x] `get_queue_message()` — single queue item lookup
  - [x] `get_batch_summary()` — aggregated pass rate per batch
  - [x] `get_product_holdings()` — product_holdings.parquet
  - [x] `get_customer_features()` — customer_features.parquet (days_since_last_login etc.)
  - [x] 5-minute TTL cache via `@st.cache_data`

### 4.5 Foundry Evaluation Pipeline

- [ ] `agents/evaluation/eval_pipeline.py` written
  - [ ] Reference-based evaluation using 30 examples in `reference_outputs/`
  - [ ] Metrics: groundedness, coherence, safety
  - [ ] Runs after each weekly batch completes
  - [ ] Outputs eval scores to results table
- [ ] Evaluation pipeline run at least once — scores produced

### 4.6 Dashboard Extension (Phase 4 scope)

- [x] `dashboard/pages/03_approved_outreach.py` created
  - [x] KPI row: total approved, email/call split, avg tokens per customer
  - [x] Bar chart: messages by churn reason; pie chart: Agent 1 confidence
  - [x] Filter by batch date, channel, churn reason
  - [x] Full message viewer (per-customer expandable text)
  - [x] Download as CSV for campaign execution
- [x] `dashboard/pages/04_review_queue.py` created (interactive)
  - [x] Violated rules frequency bar chart (top 10)
  - [x] Table of failed messages with violated rules and status
  - [x] Per-message panel: metadata, violated rules with severity, message editor
  - [x] Actions: Approve / Approve edited draft / Reject
  - [x] Write-back via `queue_store.py`; edited+approved drafts mirrored to approved_outreach
  - [x] Audit log: reviewer identity + timestamp + decision recorded
- [x] `dashboard/pages/05_pipeline_analytics.py` created
  - [x] Pass rate by churn reason
  - [x] Pass rate trend by batch
  - [x] Churn signal count vs compliance outcome
  - [x] Rule violation heatmap (rule × churn reason)
  - [x] Token cost by churn reason
  - [x] Channel selection by churn reason

**✅ Phase 4 done when:** End-to-end agent pipeline processes a test batch ✓, compliance review queue interactive in dashboard ✓, all 5 dashboard pages live ✓. Outstanding: Foundry evaluation pipeline.

---

## Phase 5 — Integration, Correlation View, and Final Validation

**Target duration:** 3–4 days
**Goal:** Full end-to-end weekly simulation, correlation dashboard live, project ready to present

### 5.1 End-to-End Weekly Simulation

- [ ] Full weekly cycle run manually:
  - [ ] Feature pipeline computes features from Population A
  - [ ] Batch scoring job scores all 50,000 customers
  - [ ] Enrichment pipeline builds ~800 profiles in Azure AI Search
  - [ ] Agent pipeline processes all 800 customers
  - [ ] Approved outreach written to table
  - [ ] Failed messages written to review queue
  - [ ] Foundry evaluation pipeline runs
  - [ ] Dashboard shows all outputs correctly
- [ ] Drift scenario simulated:
  - [ ] Population B seeded into Azure SQL
  - [ ] Feature pipeline runs — drift monitor fires
  - [ ] Event Grid triggers retraining pipeline
  - [ ] v2 trained on Population B, registered as staging
  - [ ] Canary deployment: v2 10% / v1 90%
  - [ ] Model owner reviews canary metrics and promotes v2
  - [ ] Batch scoring using v2 — precision improves on Population B data

### 5.2 Correlation Dashboard

- [ ] `dashboard/pages/05_correlation.py` extended or created
  - [ ] Weekly batch history table: `batch_date`, `model_version`, `model_precision`, `agent3_pass_rate`, `agent3_failure_rate`, `avg_groundedness_score`
  - [ ] Correlation scatter plot: `model_precision` (x) vs `agent3_pass_rate` (y) per batch
  - [ ] Diagnostic interpretation panel

### 5.3 Final Validation Checklist

- [ ] All Bicep resources deploy cleanly from scratch via GitHub Actions (no manual portal steps)
- [ ] All role assignments applied as code — no manual RBAC assignments in portal
- [x] No API keys or connection strings in any code file
- [ ] MLflow experiment shows at least 2 registered model versions (v1 and v2)
- [ ] Canary deployment comparison visible in Azure ML studio
- [ ] Drift monitor has fired at least once (from Population B simulation)
- [x] Agent pipeline processes a full batch end to end without errors
- [x] Compliance review queue interactive actions working
- [ ] Foundry evaluation pipeline has run and produced scores
- [x] All 5 dashboard pages functional and live on Streamlit Community Cloud

**✅ Phase 5 done when:** Full weekly cycle runs end to end, drift simulation complete, correlation view live, all validation checklist items ticked.

---

## Architectural Adaptations Log

Decisions made during build that deviated from the original design — kept here for reference and exam narrative.

| # | Original Plan | What Was Built | Reason |
| --- | --- | --- | --- |
| 1 | `gpt-4.1` or `gpt-4o-mini` | `gpt-oss-120b` (OpenAI-OSS format) | Azure subscription policy limits to 5 regions; none had OpenAI.GlobalStandard quota for GPT-4 family. AIServices quota pool had 5000K TPM available for gpt-oss-120b. |
| 2 | Foundry file_search vector stores for agents 2 & 3 | Inline content in system prompts | `gpt-oss-120b` format `OpenAI-OSS` does not support the `file_search` tool. Products.md (~18 KB) and rules.md (~13 KB) injected directly into prompts. |
| 3 | `text-embedding-3-large` optional | Deployed as required dependency | Foundry project requires an embedding deployment to enable project memory features. |
| 4 | Dashboard reads Azure SQL directly | Reads Azure Blob Parquet cache | Streamlit Community Cloud runs as non-root user; cannot install Microsoft ODBC Driver 18 via apt. All page-load reads use `azure-storage-blob` (pure Python). ODBC retained only for human review write-backs on page 04, extracted via `dpkg -x`. |
| 5 | `pymssql` as SQL fallback | `pyodbc` with struct-packed Entra token | `pymssql` does not accept `access_token` kwarg; Azure SQL is Entra-only (no password). Struct-packed token via `attrs_before={1256: token_struct}` is the correct pyodbc approach. |
| 6 | `ai-rg` in `swedencentral` | `germanywestcentral` | `swedencentral` not in the allowed region list for this subscription. |

---

## Content Tasks — Complete Before Phase 4

| Task | File | Status |
| --- | --- | --- |
| Product catalogue (25 offers) | `data/product_catalogue/products.md` | ✅ Complete |
| Compliance rules document | `data/compliance_rules/rules.md` | ✅ Complete |
| Reference evaluation outputs (30 examples) | `agents/evaluation/reference_outputs/` | ✅ Complete |

---

## Exam Coverage — Quick Reference

| Component | AI-103 | AI-300 |
| --- | --- | --- |
| Bicep IaC + GitHub Actions CI/CD | | ✓ |
| Azure ML feature store | | ✓ |
| MLflow experiment tracking + model registry | | ✓ |
| Canary deployment + human approval gate | | ✓ |
| Data drift + performance monitoring | | ✓ |
| Event Grid → retraining pipeline | | ✓ |
| Serverless compute configuration | | ✓ |
| Azure AI Foundry hub + project setup | ✓ | ✓ |
| gpt-oss-120b model deployment (AIServices quota) | ✓ | |
| Multi-agent orchestration (sequential pipeline) | ✓ | |
| Azure AI Search tool (Agent 1) | ✓ | |
| Inline knowledge injection (Agents 2 and 3) | ✓ | |
| Structured JSON output + schema validation | ✓ | |
| RAG pipeline with grounding | ✓ | |
| Reference-based GenAI evaluation | ✓ | ✓ |
| Content safety and compliance evaluation | ✓ | |
| Human-in-the-loop — review queue | ✓ | |
| Human-in-the-loop — model promotion gate | | ✓ |
| Managed identity + RBAC as code | ✓ | ✓ |
| Blob cache architecture (pure Python dashboard) | ✓ | ✓ |
| Correlation dashboard (ML + GenAI metrics) | | ✓ |

---

Last updated: June 2026
