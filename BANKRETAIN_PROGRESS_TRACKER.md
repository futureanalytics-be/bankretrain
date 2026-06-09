# BankRetain — Build Progress Tracker

**Customer Churn Predictor & Retention Campaign Orchestrator**
*AI-103 & AI-300 Portfolio Project*

Update this file as you complete each task. Replace `[ ]` with `[x]` when done.

---

## Progress Summary

| Phase | Status | Done When |
|---|---|---|
| Phase 1 — Infrastructure and Data | ✅ Complete | Both RGs provisioned, Population A in SQL, dashboard showing data |
| Phase 2 — ML Model and Monitoring | 🔄 In Progress | Model v1 deployed, batch scoring running, drift monitor configured |
| Phase 3 — Enrichment and Knowledge Stores | ⬜ Not Started | AI Search populated, vector stores loaded, 30 reference outputs written |
| Phase 4 — Agent Pipeline | ⬜ Not Started | Three agents working end to end, review queue live in dashboard |
| Phase 5 — Integration and Final Validation | ⬜ Not Started | Full weekly cycle runs, drift simulation complete, all 5 dashboard pages live |

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
- [x] Azure AI Foundry project (`bankretain-project`) with system-assigned managed identity
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
- [x] Key Vault (Foundry secrets)
- [x] All RBAC assignments for AI layer deployed as code

### 1.3 GitHub Actions — Infrastructure Pipeline

- [x] `deploy-infra.yml` workflow created
- [x] Triggers on push to `infra/` folder
- [x] Authenticates via GitHub Actions SP (OIDC — no stored client secret)
- [x] Deploys `ml-rg/main.bicep` first, then `ai-rg/main.bicep`
- [x] Resource IDs output to GitHub Actions environment variables

### 1.4 Synthetic Data Generation

- [x] Files placed in `data/synthetic/` folder
- [x] Python packages installed (`pandas`, `numpy`, `pyodbc`, `azure-identity`, `pyarrow`)
- [x] ODBC Driver 18 for SQL Server installed
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

**✅ Phase 1 done when:** Both resource groups provisioned via Bicep CI/CD ✓, Population A in Azure SQL, minimal dashboard showing data statistics.

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
  - [x] `salary_account_flag` (column name in SQL — same concept as salary_domiciled)
  - [x] `product_count`
  - [x] `nps_score_last`
- [x] `ml/features/feature_pipeline.py` — Azure ML pipeline: SQL → feature store
  - [x] Runs on serverless compute (Standard_DS3_v2)
  - [ ] Scheduled weekly (Sunday night)
  - [x] Uses feature pipeline compute MI for SQL access
  - [ ] Feature pipeline run tested manually at least once

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
- [ ] Model v1 registered in Azure ML model registry

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
  - [ ] Batch score job tested manually — `high_risk_batch.csv` produced (~800 rows)

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
- [ ] Promotion tested manually: v2 promoted to production in model registry

### 2.6 Dashboard Extension (Phase 2 scope)

- [x] `dashboard/pages/02_ml_monitoring.py` created
  - [x] MLflow experiment run history (precision, recall, F1, AUC per run)
  - [x] Current model version in production
  - [x] Drift signal status (green / amber / red)
  - [x] Canary split view if active (v1 vs v2 metric comparison)

**✅ Phase 2 done when:** Model v1 trained and deployed, batch scoring producing `high_risk_batch.csv`, drift monitor configured, retraining pipeline tested end to end, canary structure in place.

---

## Phase 3 — Enrichment Pipeline and Knowledge Stores

**Target duration:** 3–4 days
**Goal:** Azure AI Search populated weekly, product catalogue and compliance docs uploaded to Foundry**

### 3.1 Enrichment Pipeline

- [ ] `ml/scoring/enrichment.py` written
  - [ ] Reads `high_risk_batch.csv` from Blob Storage
  - [ ] For each high-risk customer, queries Azure SQL for:
    - [ ] Last 90 days transactions → `transaction_summary`
    - [ ] Open complaints → `complaint_summary`
    - [ ] Active products → `product_summary`
    - [ ] App sessions last 60 days → `engagement_summary`
  - [ ] Upserts profile document to Azure AI Search (`customer_id` as key)
  - [ ] Deletes profiles for customers no longer in high-risk batch
  - [ ] Writes `churn_score` from batch scoring into the profile document
- [ ] Enrichment pipeline tested on a small batch (20 customers)
- [ ] Azure AI Search index verified: profile documents present and retrievable by `customer_id`

### 3.2 Product Catalogue Content

- [ ] `data/product_catalogue/products.md` written
  - [ ] 25 synthetic Belgian retail banking retention offers
  - [ ] Each offer includes: `product_id`, `product_name`, `product_type`, `target_segment`, `eligibility_rules`, `offer_description`, `retention_use_case`, `channel_fit`
  - [ ] Coverage:
    - [ ] 6–8 offers for `price_sensitivity` (fee waivers, bonus rates, cashback)
    - [ ] 6–8 offers for `service_dissatisfaction` (priority service, dedicated contact)
    - [ ] 6–8 offers for `product_lifecycle` (mortgage renewal, rate lock, refinancing)
    - [ ] 4–6 offers for `inactivity` (re-engagement bonus, bundle discount)
- [ ] `agents/vector_stores/upload_products.py` written and run
- [ ] Product catalogue uploaded to Foundry file search vector store
- [ ] Vector store attached to Agent 2

### 3.3 Compliance Rules Content

- [ ] `data/compliance_rules/rules.md` written
  - [ ] Each rule includes: `rule_id`, `category`, `severity`, `rule_text`
  - [ ] Coverage:
    - [ ] 5–7 brand tone rules (no urgency language, professional tone)
    - [ ] 4–5 FSMA-style regulatory rules (no guaranteed return language)
    - [ ] 3–4 MiFID II-style product claim rules (no specific performance claims without caveats)
    - [ ] 2–3 personalisation requirements (must reference a specific customer signal)
    - [ ] 3–4 channel-specific rules (email unsubscribe link, call opt-out)
- [ ] `agents/vector_stores/upload_compliance.py` written and run
- [ ] Compliance rules uploaded to Foundry file search vector store
- [ ] Vector store attached to Agent 3

### 3.4 Reference Evaluation Outputs

- [ ] `agents/evaluation/reference_outputs/` folder created
- [ ] 30 manually written example good outreach messages
  - [ ] Coverage: each churn reason (4) × each channel (2) = 8 base combinations
  - [ ] Multiple customer segments represented
  - [ ] Mix of email and call script formats

**✅ Phase 3 done when:** Azure AI Search index populated from a test batch, product catalogue and compliance rules uploaded to Foundry vector stores, 30 reference outputs written.

---

## Phase 4 — Agent Pipeline

**Target duration:** 1 week
**Goal:** Three agents working end to end, compliance review queue live in dashboard**

### 4.1 Agent System Prompts

- [ ] `agents/prompts/agent1_system.md` written
  - [ ] Outputs structured JSON: `{customer_id, churn_score, churn_reason, confidence, supporting_signals}`
  - [ ] Classifies into exactly one of: `price_sensitivity`, `service_dissatisfaction`, `product_lifecycle`, `inactivity`, `unknown`
  - [ ] Sets confidence: `high` / `medium` / `low`
  - [ ] Falls back to `unknown` if fewer than 2 clear signals
- [ ] `agents/prompts/agent2_system.md` written
  - [ ] Uses file search before generating
  - [ ] Checks customer eligibility before selecting offer
  - [ ] Routes to `email` or `call` based on `channel_fit`
  - [ ] References at least one specific customer signal in message
  - [ ] Output: `{customer_id, offer_id, channel, message_draft, rationale}`
- [ ] `agents/prompts/agent3_system.md` written
  - [ ] Uses file search before evaluating
  - [ ] Any `hard_block` rule failure = immediate `fail` status
  - [ ] `flag_for_review` rules flagged but message passes if no hard blocks
  - [ ] Output: `{status: pass|fail, violated_rules: [], message_draft, review_notes}`

### 4.2 Azure AI Search Tool for Agent 1

- [ ] `agents/tools/search_tool.py` written
  - [ ] Tool name: `get_customer_profile`
  - [ ] Parameter: `customer_id` (string)
  - [ ] Filter: `customer_id eq '{customer_id}'`
  - [ ] Returns full profile document for that customer
  - [ ] Uses Foundry project MI — no API keys
- [ ] `agents/tools/schemas.py` written — JSON schema for Agent 1→2 contract
- [ ] Tool tested: returns correct profile for a given `customer_id`

### 4.3 Sequential Orchestration

- [ ] `agents/orchestration/pipeline.py` written
  - [ ] Reads `high_risk_batch.csv` from Blob Storage
  - [ ] For each customer: Agent 1 → validate JSON → Agent 2 → Agent 3 → route output
  - [ ] Pass → writes to `approved_outreach` table
  - [ ] Fail → writes to `compliance_review_queue` table
  - [ ] Every agent call logged: token count, latency, status to Foundry tracing
  - [ ] Errors handled gracefully (log and skip, do not crash pipeline)
- [ ] Pipeline tested on a batch of 20 customers end to end
- [ ] All three agents returning valid structured JSON

### 4.4 State Store for Dashboard Write-back

- [ ] `dashboard/state/queue_store.py` written
  - [ ] `approved_outreach` table: `{customer_id, offer_id, channel, message_draft, approved_at}`
  - [ ] `compliance_review_queue` table: `{customer_id, message_draft, violated_rules, review_notes, status, reviewed_by, reviewed_at}`
  - [ ] Both tables created in Azure SQL (reuses existing resource)

### 4.5 Foundry Evaluation Pipeline

- [ ] `agents/evaluation/eval_pipeline.py` written
  - [ ] Reference-based evaluation using 30 examples in `reference_outputs/`
  - [ ] Metrics: groundedness, coherence, safety
  - [ ] Runs after each weekly batch completes
  - [ ] Outputs eval scores to results table
- [ ] Evaluation pipeline run at least once — scores produced

### 4.6 Dashboard Extension (Phase 4 scope)

- [ ] `dashboard/pages/03_approved_outreach.py` created
  - [ ] Table of this week's approved messages
  - [ ] Filter by channel (email / call)
  - [ ] Filter by churn reason
  - [ ] Download as CSV for campaign execution
- [ ] `dashboard/pages/04_review_queue.py` created (interactive)
  - [ ] Table of failed messages with violated rule displayed
  - [ ] Per-message actions: Approve with justification / Edit message / Reject
  - [ ] Write-back via `queue_store.py` on action
  - [ ] Audit log: reviewer identity + timestamp + decision recorded

**✅ Phase 4 done when:** End-to-end agent pipeline processes a test batch of 20 customers successfully, compliance review queue visible and interactive in dashboard, Foundry evaluation pipeline producing scores.

---

## Phase 5 — Integration, Correlation View, and Final Validation

**Target duration:** 3–4 days
**Goal:** Full end-to-end weekly simulation, correlation dashboard live, project ready to present**

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

- [ ] `dashboard/pages/05_correlation.py` created
  - [ ] Weekly batch history table: `batch_date`, `model_version`, `model_precision`, `agent3_pass_rate`, `agent3_failure_rate`, `avg_groundedness_score`
  - [ ] Correlation scatter plot: `model_precision` (x) vs `agent3_pass_rate` (y) per batch
  - [ ] Diagnostic interpretation panel:
    - [ ] Both metrics drop → "Model flags propagating through pipeline — review ML layer"
    - [ ] Agent 3 failure spikes, precision stable → "GenAI layer issue — review prompts or knowledge stores"
    - [ ] Precision drops, Agent 3 stable → "Model degrading — retraining likely needed soon"

### 5.3 Final Validation Checklist

- [ ] All Bicep resources deploy cleanly from scratch via GitHub Actions (no manual portal steps)
- [ ] All role assignments applied as code — no manual RBAC assignments in portal
- [ ] No API keys or connection strings in any code file
- [ ] MLflow experiment shows at least 2 registered model versions (v1 and v2)
- [ ] Canary deployment comparison visible in Azure ML studio
- [ ] Drift monitor has fired at least once (from Population B simulation)
- [ ] Agent pipeline processes a full batch end to end without errors
- [ ] Compliance review queue interactive actions working
- [ ] Foundry evaluation pipeline has run and produced scores
- [ ] All 5 dashboard pages functional

**✅ Phase 5 done when:** Full weekly cycle runs end to end, drift simulation complete, correlation view live, all validation checklist items ticked.

---

## Content Tasks — Complete Before Phase 4

These are writing tasks, not code tasks. Both must be finished before starting Phase 4.

| Task | File | Status |
|---|---|---|
| Product catalogue (25 offers) | `data/product_catalogue/products.md` | ⬜ Not Started |
| Compliance rules document | `data/compliance_rules/rules.md` | ⬜ Not Started |
| Reference evaluation outputs (30 examples) | `agents/evaluation/reference_outputs/` | ⬜ Not Started |

---

## Exam Coverage — Quick Reference

| Component | AI-103 | AI-300 |
|---|---|---|
| Bicep IaC + GitHub Actions CI/CD | | ✓ |
| Azure ML feature store | | ✓ |
| MLflow experiment tracking + model registry | | ✓ |
| Canary deployment + human approval gate | | ✓ |
| Data drift + performance monitoring | | ✓ |
| Event Grid → retraining pipeline | | ✓ |
| Serverless compute configuration | | ✓ |
| Azure AI Foundry hub + project setup | ✓ | ✓ |
| GPT-4o model deployment | ✓ | |
| Multi-agent orchestration (Foundry Agent Service) | ✓ | |
| Azure AI Search tool (Agent 1) | ✓ | |
| Foundry file search (Agents 2 and 3) | ✓ | |
| Structured JSON output + schema validation | ✓ | |
| RAG pipeline with grounding | ✓ | |
| Reference-based GenAI evaluation | ✓ | ✓ |
| Content safety and compliance evaluation | ✓ | |
| Human-in-the-loop — review queue | ✓ | |
| Human-in-the-loop — model promotion gate | | ✓ |
| Managed identity + RBAC as code | ✓ | ✓ |
| Correlation dashboard (ML + GenAI metrics) | | ✓ |

---

*Last updated: June 2026*
