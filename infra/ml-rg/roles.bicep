// =============================================================================
// BankRetain — RBAC Module (ML layer)
// All role assignments for bankretain-ml-rg as code.
// Principle: every identity gets the minimum role needed for its function only.
// =============================================================================

targetScope = 'resourceGroup'

param amlWorkspacePrincipalId string       // AML workspace system-assigned MI
param featurePipelineMIPrincipalId string  // Feature pipeline user-assigned MI
param storageAccountName string
param sqlServerName string
param keyVaultName string
param developerObjectId string             // Empty string in prod — key vault admin removed
param githubActionsPrincipalId string
param environment string

// ---------------------------------------------------------------------------
// Built-in role definition IDs (stable across all Azure tenants)
// ---------------------------------------------------------------------------

var roleStorageBlobDataContributor = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
var roleStorageBlobDataReader      = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1')
var roleKeyVaultSecretsUser        = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
var roleKeyVaultAdministrator      = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '00482a5a-887f-4fb3-b363-3b7fe8e74483')
var roleContributor                = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b24988ac-6180-42a0-ab88-20f7382dd24c')
var roleAzureMLComputeOperator     = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'e503ece1-11d0-4e8e-8e2c-7a6c3bf38815')

// ---------------------------------------------------------------------------
// Reference existing resources by name
// ---------------------------------------------------------------------------

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' existing = {
  name: storageAccountName
}

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}

// ---------------------------------------------------------------------------
// Feature Pipeline MI → Storage: Storage Blob Data Contributor
// Reads feature snapshots and writes scoring outputs to Blob
// ---------------------------------------------------------------------------

resource featurePipelineMI_Storage_Contributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, featurePipelineMIPrincipalId, roleStorageBlobDataContributor)
  scope: storageAccount
  properties: {
    roleDefinitionId: roleStorageBlobDataContributor
    principalId: featurePipelineMIPrincipalId
    principalType: 'ServicePrincipal'
    description: 'Feature pipeline MI writes feature snapshots and batch scoring outputs'
  }
}

// ---------------------------------------------------------------------------
// AML Workspace MI → Storage: Storage Blob Data Contributor
// AML internal service communication needs read/write to default storage
// ---------------------------------------------------------------------------

resource amlWorkspaceMI_Storage_Contributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, amlWorkspacePrincipalId, roleStorageBlobDataContributor)
  scope: storageAccount
  properties: {
    roleDefinitionId: roleStorageBlobDataContributor
    principalId: amlWorkspacePrincipalId
    principalType: 'ServicePrincipal'
    description: 'AML workspace MI reads/writes feature store artifacts and pipeline outputs'
  }
}

// ---------------------------------------------------------------------------
// Feature Pipeline MI → Key Vault: Key Vault Secrets User
// Reads SQL connection string at runtime — cannot manage or delete secrets
// ---------------------------------------------------------------------------

resource featurePipelineMI_KeyVault_SecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, featurePipelineMIPrincipalId, roleKeyVaultSecretsUser)
  scope: keyVault
  properties: {
    roleDefinitionId: roleKeyVaultSecretsUser
    principalId: featurePipelineMIPrincipalId
    principalType: 'ServicePrincipal'
    description: 'Feature pipeline MI reads SQL connection string at runtime'
  }
}

// ---------------------------------------------------------------------------
// AML Workspace MI → Key Vault: Key Vault Secrets User
// ---------------------------------------------------------------------------

resource amlWorkspaceMI_KeyVault_SecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, amlWorkspacePrincipalId, roleKeyVaultSecretsUser)
  scope: keyVault
  properties: {
    roleDefinitionId: roleKeyVaultSecretsUser
    principalId: amlWorkspacePrincipalId
    principalType: 'ServicePrincipal'
    description: 'AML workspace MI reads secrets at runtime'
  }
}

// ---------------------------------------------------------------------------
// GitHub Actions SP → Key Vault: Key Vault Secrets User
// Needed for CI/CD pipelines that reference secrets
// ---------------------------------------------------------------------------

resource githubActions_KeyVault_SecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, githubActionsPrincipalId, roleKeyVaultSecretsUser)
  scope: keyVault
  properties: {
    roleDefinitionId: roleKeyVaultSecretsUser
    principalId: githubActionsPrincipalId
    principalType: 'ServicePrincipal'
    description: 'GitHub Actions SP reads secrets for CI/CD pipelines'
  }
}

// ---------------------------------------------------------------------------
// GitHub Actions SP → Resource Group: Contributor (RG-scoped)
// Allows infrastructure provisioning — not subscription-level Owner
// ---------------------------------------------------------------------------

resource githubActions_RG_Contributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, githubActionsPrincipalId, roleContributor)
  properties: {
    roleDefinitionId: roleContributor
    principalId: githubActionsPrincipalId
    principalType: 'ServicePrincipal'
    description: 'GitHub Actions SP deploys Bicep templates to bankretain-ml-rg'
  }
}

// ---------------------------------------------------------------------------
// Developer Identity → Key Vault: Key Vault Administrator (dev only)
// Used during initial setup to create secrets. Omit in prod (empty string check).
// ---------------------------------------------------------------------------

resource developer_KeyVault_Administrator 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(developerObjectId) && environment == 'dev') {
  name: guid(keyVault.id, developerObjectId, roleKeyVaultAdministrator)
  scope: keyVault
  properties: {
    roleDefinitionId: roleKeyVaultAdministrator
    principalId: developerObjectId
    principalType: 'User'
    description: 'Developer manages Key Vault secrets during initial setup — dev environment only'
  }
}

// ---------------------------------------------------------------------------
// NOTE: Feature Pipeline MI → Azure SQL (db_datareader) is a SQL-level
// role, not an ARM role — it must be granted via T-SQL after deployment:
//
//   CREATE USER [bankretain-mi-featurepipeline-dev]
//     FROM EXTERNAL PROVIDER;
//   ALTER ROLE db_datareader
//     ADD MEMBER [bankretain-mi-featurepipeline-dev];
//
// See: data/synthetic/seed_sql.py for the post-deployment SQL setup script.
// ---------------------------------------------------------------------------
