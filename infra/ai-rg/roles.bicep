// =============================================================================
// BankRetain — RBAC Module (AI layer)
// All role assignments for bankretain-ai-rg as code.
//
// Critical isolation rule:
//   Foundry project MI → AI Search READ only (Search Index Data Reader)
//   Feature pipeline MI → AI Search WRITE (Search Index Data Contributor)
//   Foundry project MI has ZERO access to Azure SQL or Azure ML layer
// =============================================================================

targetScope = 'resourceGroup'

param foundryProjectPrincipalId string    // Foundry project system-assigned MI
param featurePipelineMIPrincipalId string  // Feature pipeline user-assigned MI (from ml-rg)
param searchServiceName string
param keyVaultName string
param developerObjectId string
param githubActionsPrincipalId string
param environment string

// ---------------------------------------------------------------------------
// Built-in role definition IDs
// ---------------------------------------------------------------------------

var roleSearchIndexDataContributor = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '8ebe5a00-799e-43f5-93ac-243d3dce84a7')
var roleSearchIndexDataReader      = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '1407120a-92aa-4202-b7e9-c0e197c71c8f')
var roleKeyVaultSecretsUser        = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
var roleKeyVaultAdministrator      = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '00482a5a-887f-4fb3-b363-3b7fe8e74483')
var roleContributor                = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b24988ac-6180-42a0-ab88-20f7382dd24c')

// ---------------------------------------------------------------------------
// Reference existing resources
// ---------------------------------------------------------------------------

resource searchService 'Microsoft.Search/searchServices@2023-11-01' existing = {
  name: searchServiceName
}

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}

// ---------------------------------------------------------------------------
// Search RBAC — prod only (Free tier does not support managed identity auth)
// In dev, agents and enrichment pipeline use API key stored in Key Vault
// ---------------------------------------------------------------------------

resource featurePipelineMI_Search_Contributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (environment == 'prod') {
  name: guid(searchService.id, featurePipelineMIPrincipalId, roleSearchIndexDataContributor)
  scope: searchService
  properties: {
    roleDefinitionId: roleSearchIndexDataContributor
    principalId: featurePipelineMIPrincipalId
    principalType: 'ServicePrincipal'
    description: 'Feature pipeline MI upserts/deletes customer profile documents in AI Search weekly'
  }
}

resource foundryProjectMI_Search_Reader 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (environment == 'prod') {
  name: guid(searchService.id, foundryProjectPrincipalId, roleSearchIndexDataReader)
  scope: searchService
  properties: {
    roleDefinitionId: roleSearchIndexDataReader
    principalId: foundryProjectPrincipalId
    principalType: 'ServicePrincipal'
    description: 'Foundry project MI queries customer profiles for Agent 1 — read-only'
  }
}

// ---------------------------------------------------------------------------
// Foundry Project MI → Key Vault: Key Vault Secrets User
// Agent runtime reads AI Search endpoint from Key Vault
// ---------------------------------------------------------------------------

resource foundryProjectMI_KeyVault_SecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, foundryProjectPrincipalId, roleKeyVaultSecretsUser)
  scope: keyVault
  properties: {
    roleDefinitionId: roleKeyVaultSecretsUser
    principalId: foundryProjectPrincipalId
    principalType: 'ServicePrincipal'
    description: 'Foundry project MI reads agent configuration secrets at runtime'
  }
}

// ---------------------------------------------------------------------------
// Feature Pipeline MI → Key Vault: Key Vault Secrets User
// Enrichment pipeline reads AI Search endpoint at runtime
// ---------------------------------------------------------------------------

resource featurePipelineMI_KeyVault_SecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, featurePipelineMIPrincipalId, roleKeyVaultSecretsUser)
  scope: keyVault
  properties: {
    roleDefinitionId: roleKeyVaultSecretsUser
    principalId: featurePipelineMIPrincipalId
    principalType: 'ServicePrincipal'
    description: 'Feature pipeline MI reads AI Search endpoint to upsert profiles'
  }
}

// ---------------------------------------------------------------------------
// GitHub Actions SP → Key Vault: Key Vault Secrets User
// ---------------------------------------------------------------------------

resource githubActions_KeyVault_SecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, githubActionsPrincipalId, roleKeyVaultSecretsUser)
  scope: keyVault
  properties: {
    roleDefinitionId: roleKeyVaultSecretsUser
    principalId: githubActionsPrincipalId
    principalType: 'ServicePrincipal'
    description: 'GitHub Actions SP reads secrets during CI/CD pipelines'
  }
}

// ---------------------------------------------------------------------------
// GitHub Actions SP → Resource Group: Contributor (RG-scoped)
// ---------------------------------------------------------------------------

resource githubActions_RG_Contributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, githubActionsPrincipalId, roleContributor)
  properties: {
    roleDefinitionId: roleContributor
    principalId: githubActionsPrincipalId
    principalType: 'ServicePrincipal'
    description: 'GitHub Actions SP deploys Bicep templates to bankretain-ai-rg'
  }
}

// ---------------------------------------------------------------------------
// Developer Identity → Key Vault: Key Vault Administrator (dev only)
// ---------------------------------------------------------------------------

resource developer_KeyVault_Administrator 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(developerObjectId) && environment == 'dev') {
  name: guid(keyVault.id, developerObjectId, roleKeyVaultAdministrator)
  scope: keyVault
  properties: {
    roleDefinitionId: roleKeyVaultAdministrator
    principalId: developerObjectId
    principalType: 'User'
    description: 'Developer manages Foundry layer secrets during initial setup — dev only'
  }
}
