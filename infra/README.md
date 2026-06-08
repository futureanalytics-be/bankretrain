# BankRetain — Infrastructure

## Overview

BankRetain is a churn prediction and retention pipeline for a banking workload. It scores ~50,000 customers weekly, identifies the ~800 highest-risk customers, generates personalised retention offers via AI agents, and evaluates those offers for compliance before they are sent.

The infrastructure is split into two independently deployable Azure resource groups:

| Layer | Resource Group | Purpose |
|---|---|---|
| ML | `bankretain-ml-rg` | Data ingestion, feature engineering, batch scoring, feature store |
| AI | `bankretain-ai-rg` | Agent orchestration, LLM inference, customer profile search index |

Region: **Sweden Central** for both layers.

---

## Architecture

```
bankretain-ml-rg                         bankretain-ai-rg
─────────────────────────────────        ──────────────────────────────────
 Azure SQL (Entra-only auth)              Azure AI Foundry Hub
 Azure ML Workspace                         └─ GPT-4o deployment
 Azure ML Feature Store                   Azure AI Foundry Project
 Storage Account (shared)                   └─ Agent 1: churn classifier
 Container Registry                         └─ Agent 2: offer generator
 Key Vault (ml secrets)                     └─ Agent 3: compliance evaluator
 Log Analytics + App Insights             Azure AI Search (customer profiles)
 User-Assigned MI (feature pipeline)      Key Vault (ai secrets)
                                          Log Analytics
                                          Storage Account (foundry default)
```

The feature pipeline MI (created in `ml-rg`) crosses the boundary: it writes enriched customer profiles to AI Search in `ai-rg`. Everything else is scoped to its own layer.

---

## Resource Inventory

### `bankretain-ml-rg`

| Resource | Bicep Module | Notes |
|---|---|---|
| Azure SQL Server | `sql.bicep` | Entra-only auth; developer account as Entra admin |
| Azure SQL Database | `sql.bicep` | GeneralPurpose Serverless Gen5 1vCore; free limit with auto-pause |
| Storage Account | `sql.bicep` | Shared by AML workspace and feature store |
| Key Vault | `sql.bicep` | Stores SQL connection string (MI auth format) |
| Log Analytics Workspace | `aml.bicep` | Backing store for Application Insights |
| Application Insights | `aml.bicep` | Attached to AML workspace |
| Container Registry | `aml.bicep` | Basic tier; admin user disabled (MI-only) |
| Azure ML Workspace | `aml.bicep` | System-assigned MI; v2 mode |
| Azure ML Feature Store | `aml.bicep` | Separate workspace (`kind: FeatureStore`); Spark 3.4 runtime |
| User-Assigned MI | `aml.bicep` | `bankretain-mi-featurepipeline-{env}` — identity for feature pipeline compute |
| RBAC assignments | `roles.bicep` | See RBAC section below |

### `bankretain-ai-rg`

| Resource | Bicep Module | Notes |
|---|---|---|
| Azure AI Foundry Hub | `foundry.bicep` | Shared infra layer; system-assigned MI |
| Azure AI Foundry Project | `foundry.bicep` | Scopes all three agents; system-assigned MI |
| Azure AI Search | `search.bicep` | Basic tier; RBAC auth; semantic search disabled |
| Key Vault | `foundry.bicep` | AI Search endpoint for agent runtime bootstrap |
| Log Analytics Workspace | `foundry.bicep` | Foundry diagnostics |
| Storage Account | `foundry.bicep` | Foundry hub default storage |
| RBAC assignments | `roles.bicep` | See RBAC section below |

---

## RBAC Matrix

All role assignments are defined as code in `roles.bicep` for each layer. No role is broader than needed.

### ML layer (`bankretain-ml-rg`)

| Identity | Resource | Role | Reason |
|---|---|---|---|
| Feature pipeline MI | Storage Account | Storage Blob Data Contributor | Reads snapshots, writes scoring outputs |
| AML Workspace MI | Storage Account | Storage Blob Data Contributor | AML internal service communication |
| Feature pipeline MI | Key Vault | Key Vault Secrets User | Reads SQL connection string at runtime |
| AML Workspace MI | Key Vault | Key Vault Secrets User | Reads secrets at runtime |
| GitHub Actions SP | Key Vault | Key Vault Secrets User | CI/CD pipeline secret access |
| GitHub Actions SP | Resource Group | Contributor | Deploys Bicep templates |
| Developer (dev only) | Key Vault | Key Vault Administrator | Initial secret setup |

### AI layer (`bankretain-ai-rg`)

| Identity | Resource | Role | Reason |
|---|---|---|---|
| Feature pipeline MI | AI Search | Search Index Data Contributor | Upserts/deletes customer profile documents weekly |
| Foundry Project MI | AI Search | Search Index Data Reader | Agents query profiles — read-only, cannot modify |
| Foundry Project MI | Key Vault | Key Vault Secrets User | Reads AI Search endpoint at agent runtime |
| Feature pipeline MI | Key Vault | Key Vault Secrets User | Reads AI Search endpoint for enrichment pipeline |
| GitHub Actions SP | Key Vault | Key Vault Secrets User | CI/CD pipeline secret access |
| GitHub Actions SP | Resource Group | Contributor | Deploys Bicep templates |
| Developer (dev only) | Key Vault | Key Vault Administrator | Initial secret setup |

**Isolation rule:** The Foundry project MI has zero access to Azure SQL or the Azure ML layer. The feature pipeline MI has write access to AI Search but read-only access to SQL (granted via T-SQL, not ARM).

---

## AI Search Index Schema

The index (`customer-profiles`) is created by the enrichment pipeline on first run — ARM does not support index CRUD. The schema is documented in `search.bicep`.

Only ~800 high-risk customers per week are indexed (not all 50,000). Agent 1 uses filtered exact lookup (`$filter=customer_id eq 'C00142'`), not semantic search.

**Post-deployment T-SQL required** to grant the feature pipeline MI database access:

```sql
CREATE USER [bankretain-mi-featurepipeline-dev] FROM EXTERNAL PROVIDER;
ALTER ROLE db_datareader ADD MEMBER [bankretain-mi-featurepipeline-dev];
ALTER ROLE db_datawriter ADD MEMBER [bankretain-mi-featurepipeline-dev];
```

---

## Deployment Pipeline

`.github/workflows/deploy-infra.yml` — triggers on push to `infra/**` or manual dispatch.

```
validate ──► deploy-ml-rg ──► deploy-ai-rg ──► validate-deployment
```

**Job order is enforced:** `deploy-ai-rg` needs the `featurePipelineMIPrincipalId` output from `deploy-ml-rg` to wire up AI Search RBAC. A null guard fails the job immediately if the output is missing.

**Auth:** OIDC federated identity — no client secret stored in GitHub. The GitHub Actions SP authenticates via a federated credential scoped to `repo:LanreAdetola/bankretain:ref:refs/heads/main`.

**Required GitHub secrets:**

| Secret | Value |
|---|---|
| `AZURE_CLIENT_ID` | GitHub Actions SP app ID (`941def67-...`) |
| `AZURE_SUBSCRIPTION_ID` | Subscription ID |
| `AZURE_TENANT_ID` | Tenant ID |
| `DEVELOPER_OBJECT_ID` | Developer Entra object ID (used as SQL Entra admin) |
| `ACTIONS_SP_OBJECT_ID` | GitHub Actions SP object ID |

---

## Design Decisions

### Two resource groups instead of one

The ML and AI layers have different change cadences, different access patterns, and different cost centres. Splitting them means an agent config change doesn't require redeploying the SQL server, and vice versa. It also makes it straightforward to delete the AI layer without touching training data.

### Entra-only authentication for Azure SQL

SQL admin passwords are eliminated entirely. The developer Entra account is set as the Entra admin on the SQL server at provisioning time (`azureADOnlyAuthentication: true`). The feature pipeline MI connects using `Authentication=Active Directory MSI` in the connection string. This removes a rotation burden and a secret from the deployment pipeline.

### User-assigned MI for the feature pipeline, system-assigned for everything else

The feature pipeline MI (`bankretain-mi-featurepipeline-{env}`) is user-assigned because it must be granted roles in both `ml-rg` (storage, Key Vault) and `ai-rg` (AI Search, Key Vault) — its identity needs to be known before those role assignments are made. System-assigned MIs on the AML workspace and Foundry project/hub are sufficient for those resources because their roles are scoped to their own layer.

### Foundry Hub + Project pattern

The hub is the shared infrastructure layer (storage, Key Vault, networking). The project scopes the three agents and their tools. This matches the Azure AI Foundry recommended topology and allows additional projects to share the hub in future without duplication.

### AI Search Basic tier with RBAC auth, semantic search disabled

Agents use filtered exact lookup on `customer_id` — semantic ranking would add cost and latency with no benefit. Basic tier provides one replica and three partitions, which is sufficient for ~800 documents per week. RBAC auth is enabled; API key auth is left enabled in dev for debugging and should be disabled in prod.

### `uniqueString()` for resource naming

All resource names use `uniqueString(resourceGroup().id)` as a suffix. This makes names deterministic (same RG ID always produces the same name), idempotent across re-deployments, globally unique within Azure's namespace constraints, and free of manual coordination.

### OIDC over stored client secrets for GitHub Actions

No credentials are stored in GitHub secrets. The federated identity credential is scoped to the exact branch (`refs/heads/main`), so a token issued to a PR branch or a fork cannot authenticate against the subscription.

### Pre-flight validation before every deploy

A `validate` job runs `az deployment group validate` on both templates before any resource is touched. This catches parameter mismatches, invalid role definition IDs, and ARM schema errors without consuming deployment quota or modifying state.

### Concurrency lock on the deployment workflow

`concurrency: cancel-in-progress: false` queues a second run rather than cancelling it. Cancelling mid-deployment leaves resources in a partially-provisioned state that is difficult to recover from. Queuing ensures the in-flight deployment finishes cleanly first.
