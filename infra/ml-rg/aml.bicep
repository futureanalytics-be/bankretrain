// =============================================================================
// BankRetain — Azure ML Module (ML layer)
// Deploys: Log Analytics, Application Insights, Azure ML workspace,
//          Azure ML managed feature store, user-assigned MI for feature pipeline
// =============================================================================

targetScope = 'resourceGroup'

param location string
param environment string
param storageAccountName string  // passed from sql.bicep output

// ---------------------------------------------------------------------------
// Naming
// ---------------------------------------------------------------------------

var suffix = uniqueString(resourceGroup().id)
var logAnalyticsName = 'bankretain-law-${environment}-${take(suffix, 8)}'
var appInsightsName = 'bankretain-appi-${environment}-${take(suffix, 8)}'
var amlWorkspaceName = 'bankretain-aml-${environment}-${take(suffix, 8)}'
var featureStoreName = 'bankretain-fs-${environment}-${take(suffix, 8)}'
var featurePipelineMIName = 'bankretain-mi-featurepipeline-${environment}'
var containerRegistryName = 'bankretaincr${environment}${take(suffix, 8)}'

// ---------------------------------------------------------------------------
// Log Analytics Workspace (required by Application Insights)
// ---------------------------------------------------------------------------

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: logAnalyticsName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
  tags: {
    project: 'bankretain'
    environment: environment
    layer: 'ml'
  }
}

// ---------------------------------------------------------------------------
// Application Insights (attached to Azure ML workspace)
// ---------------------------------------------------------------------------

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
    RetentionInDays: 30
  }
  tags: {
    project: 'bankretain'
    environment: environment
    layer: 'ml'
  }
}

// ---------------------------------------------------------------------------
// Container Registry (required by Azure ML workspace)
// ---------------------------------------------------------------------------

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: containerRegistryName
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false  // MI-only access
  }
  tags: {
    project: 'bankretain'
    environment: environment
    layer: 'ml'
  }
}

// ---------------------------------------------------------------------------
// Reference to existing Storage Account (created in sql.bicep)
// ---------------------------------------------------------------------------

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' existing = {
  name: storageAccountName
}

// ---------------------------------------------------------------------------
// User-Assigned Managed Identity — Feature Pipeline Compute
// This MI gets: SQL db_datareader, AI Search Index Data Contributor,
//               Blob Storage Blob Data Contributor
// ---------------------------------------------------------------------------

resource featurePipelineMI 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: featurePipelineMIName
  location: location
  tags: {
    project: 'bankretain'
    environment: environment
    purpose: 'feature-pipeline-compute'
  }
}

// ---------------------------------------------------------------------------
// Azure ML Workspace
// System-assigned MI enabled — used for internal AML service communication
// ---------------------------------------------------------------------------

resource amlWorkspace 'Microsoft.MachineLearningServices/workspaces@2024-01-01-preview' = {
  name: amlWorkspaceName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    friendlyName: 'BankRetain ML Workspace'
    description: 'Azure ML workspace for BankRetain churn prediction pipeline'
    storageAccount: storageAccount.id
    applicationInsights: appInsights.id
    containerRegistry: containerRegistry.id
    publicNetworkAccess: 'Enabled'
    v1LegacyMode: false
  }
  tags: {
    project: 'bankretain'
    environment: environment
    layer: 'ml'
  }
}

// ---------------------------------------------------------------------------
// Azure ML Managed Feature Store
// Separate workspace with kind=FeatureStore for training-serving consistency
// ---------------------------------------------------------------------------

resource featureStore 'Microsoft.MachineLearningServices/workspaces@2024-01-01-preview' = {
  name: featureStoreName
  location: location
  kind: 'FeatureStore'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    friendlyName: 'BankRetain Feature Store'
    description: 'Managed feature store ensuring training-serving consistency for churn model'
    storageAccount: storageAccount.id
    applicationInsights: appInsights.id
    publicNetworkAccess: 'Enabled'
    featureStoreSettings: {
      computeRuntime: {
        sparkRuntimeVersion: '3.4'
      }
    }
  }
  tags: {
    project: 'bankretain'
    environment: environment
    layer: 'ml'
    purpose: 'feature-store'
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------

output amlWorkspaceName string = amlWorkspace.name
output amlWorkspaceId string = amlWorkspace.id
output amlWorkspacePrincipalId string = amlWorkspace.identity.principalId
output featureStoreName string = featureStore.name
output featurePipelineMIName string = featurePipelineMI.name
output featurePipelineMIClientId string = featurePipelineMI.properties.clientId
output featurePipelineMIPrincipalId string = featurePipelineMI.properties.principalId
output appInsightsConnectionString string = appInsights.properties.ConnectionString
