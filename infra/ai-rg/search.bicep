// =============================================================================
// BankRetain — Azure AI Search Module (AI layer)
// Deploys: Azure AI Search service (Basic tier) + customer profile index
//
// Index design rationale:
//   - Only ~800 high-risk customers per week are indexed (not all 50,000)
//   - customer_id is the precise lookup key for Agent 1 filtered retrieval
//   - Numeric fields are filterable for enrichment pipeline upserts
//   - *_summary fields are searchable narrative strings — human-readable,
//     built by enrichment.py via deterministic templating (not LLMs)
// =============================================================================

targetScope = 'resourceGroup'

param location string
param environment string

// ---------------------------------------------------------------------------
// Naming
// ---------------------------------------------------------------------------

var suffix = uniqueString(resourceGroup().id)
var searchServiceName = 'bankretain-search-${environment}-${take(suffix, 8)}'

// Free tier in dev: no MI, no RBAC auth, 50 MB storage — sufficient for testing ~800 docs
// Basic tier in prod: system-assigned MI, RBAC auth, 15 GB storage
var isProd = environment == 'prod'

// ---------------------------------------------------------------------------
// Azure AI Search
// dev  → Free  (API key auth, no MI — agents use key from Key Vault)
// prod → Basic (RBAC auth via system-assigned MI)
// ---------------------------------------------------------------------------

resource searchService 'Microsoft.Search/searchServices@2023-11-01' = {
  name: searchServiceName
  location: location
  sku: {
    name: isProd ? 'basic' : 'free'
  }
  identity: isProd ? {
    type: 'SystemAssigned'
  } : null
  properties: {
    replicaCount: 1
    partitionCount: 1
    hostingMode: 'default'
    publicNetworkAccess: 'enabled'
    authOptions: isProd ? {
      aadOrApiKey: {
        aadAuthFailureMode: 'http403'
      }
    } : null
    semanticSearch: 'disabled'
  }
  tags: {
    project: 'bankretain'
    environment: environment
    layer: 'ai'
    purpose: 'customer-profile-index'
  }
}

// ---------------------------------------------------------------------------
// Customer Profile Index
//
// Schema mirrors the enrichment pipeline output (see ml/scoring/enrichment.py)
// Filterable fields: used in Agent 1 tool call ($filter=customer_id eq 'C00142')
// Searchable fields: narrative summaries retrieved by Agent 1 for reasoning
//
// NOTE: Index creation via ARM/Bicep deploys the schema definition.
//       The actual index must be created via the Search REST API or SDK
//       after the service is provisioned (ARM does not support index CRUD).
//       See: ml/scoring/enrichment.py — create_or_update_index() function.
// ---------------------------------------------------------------------------

// The index schema is defined here as a deployment script reference comment
// for documentation. The actual index is created by enrichment.py on first run.
//
// Index name: customer-profiles
// Fields:
//   customer_id            — Edm.String  — key=true,  filterable=true,  retrievable=true
//   snapshot_date          — Edm.String  — key=false, filterable=true,  retrievable=true
//   churn_score            — Edm.Double  — key=false, filterable=true,  retrievable=true, sortable=true
//   days_since_last_login  — Edm.Int32   — key=false, filterable=true,  retrievable=true
//   complaints_open        — Edm.Int32   — key=false, filterable=true,  retrievable=true
//   competitor_transfer_cnt— Edm.Int32   — key=false, filterable=true,  retrievable=true
//   months_to_rate_reset   — Edm.Double  — key=false, filterable=true,  retrievable=true
//   segment                — Edm.String  — key=false, filterable=true,  retrievable=true, facetable=true
//   region                 — Edm.String  — key=false, filterable=true,  retrievable=true, facetable=true
//   product_summary        — Edm.String  — key=false, searchable=true,  retrievable=true
//   engagement_summary     — Edm.String  — key=false, searchable=true,  retrievable=true
//   complaint_summary      — Edm.String  — key=false, searchable=true,  retrievable=true
//   transaction_summary    — Edm.String  — key=false, searchable=true,  retrievable=true

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------

output searchServiceName string = searchService.name
output searchServiceId string = searchService.id
output searchServiceEndpoint string = 'https://${searchService.name}.search.windows.net'
output searchServicePrincipalId string = isProd ? searchService.identity.principalId : ''
