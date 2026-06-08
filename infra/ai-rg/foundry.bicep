// =============================================================================
// BankRetain — Azure AI Foundry Module (AI layer)
// Deploys: Log Analytics, Storage (Foundry default), Azure AI Foundry hub,
//          Azure AI Foundry project (bankretain-project), Key Vault
// =============================================================================

targetScope = 'resourceGroup'

param location string
param environment string

// ---------------------------------------------------------------------------
// Naming
// ---------------------------------------------------------------------------

var suffix = uniqueString(resourceGroup().id)
var lawName = 'bankretain-ai-law-${environment}-${take(suffix, 8)}'
var storageAccountName = 'bankretainai${environment}${take(suffix, 8)}'
var foundryHubName = 'bankretain-hub-${environment}-${take(suffix, 8)}'
var foundryProjectName = 'bankretain-project'
var keyVaultName = 'bankretain-kv-ai-${take(suffix, 8)}'

// ---------------------------------------------------------------------------
// Log Analytics (for Foundry diagnostics)
// ---------------------------------------------------------------------------

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: lawName
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
  tags: {
    project: 'bankretain'
    environment: environment
    layer: 'ai'
  }
}

// ---------------------------------------------------------------------------
// Storage Account (Foundry hub default storage)
// ---------------------------------------------------------------------------

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
  tags: {
    project: 'bankretain'
    environment: environment
    layer: 'ai'
  }
}

// ---------------------------------------------------------------------------
// Key Vault — Foundry layer secrets (AI Search key for agent bootstrap)
// ---------------------------------------------------------------------------

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  properties: {
    sku: { family: 'A', name: 'standard' }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    enabledForTemplateDeployment: true
    publicNetworkAccess: 'Enabled'
  }
  tags: {
    project: 'bankretain'
    environment: environment
    layer: 'ai'
  }
}

// ---------------------------------------------------------------------------
// Azure AI Foundry Hub
// The hub is the shared infrastructure layer — GPT-4o deployment lives here.
// System-assigned MI is created automatically on the hub.
// ---------------------------------------------------------------------------

resource foundryHub 'Microsoft.MachineLearningServices/workspaces@2024-01-01-preview' = {
  name: foundryHubName
  location: location
  kind: 'Hub'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    friendlyName: 'BankRetain AI Hub'
    description: 'Foundry hub for BankRetain agent pipeline — GPT-4o, Agent Service, file search'
    storageAccount: storageAccount.id
    keyVault: keyVault.id
    publicNetworkAccess: 'Enabled'
  }
  tags: {
    project: 'bankretain'
    environment: environment
    layer: 'ai'
  }
}

// ---------------------------------------------------------------------------
// Azure AI Foundry Project
// The project scopes the three agents (Agent 1, 2, 3) and their tools.
// System-assigned MI on the project is used at agent runtime to query AI Search.
// ---------------------------------------------------------------------------

resource foundryProject 'Microsoft.MachineLearningServices/workspaces@2024-01-01-preview' = {
  name: foundryProjectName
  location: location
  kind: 'Project'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    friendlyName: 'BankRetain Project'
    description: 'Foundry project for BankRetain: churn reason classification, offer generation, compliance evaluation'
    hubResourceId: foundryHub.id
    publicNetworkAccess: 'Enabled'
  }
  tags: {
    project: 'bankretain'
    environment: environment
    layer: 'ai'
    purpose: 'agent-pipeline'
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------

output foundryHubName string = foundryHub.name
output foundryHubId string = foundryHub.id
output foundryProjectName string = foundryProject.name
output foundryProjectId string = foundryProject.id
output foundryProjectPrincipalId string = foundryProject.identity.principalId
output keyVaultName string = keyVault.name
output keyVaultId string = keyVault.id
output storageAccountName string = storageAccount.name
