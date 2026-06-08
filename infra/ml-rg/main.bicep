// =============================================================================
// BankRetain — ML Resource Group
// bankretain-ml-rg
// Deploys: Azure SQL, Azure ML workspace, managed feature store,
//          Storage Account, Key Vault, user-assigned MI
// Region: Sweden Central
// =============================================================================

targetScope = 'resourceGroup'

@description('Environment tag (dev | prod)')
param environment string = 'dev'

@description('Azure region for all resources')
param location string = 'switzerlandnorth'

@description('Object ID of the developer Entra ID user — for Key Vault Administrator in dev')
param developerObjectId string = ''

@description('Object ID of the GitHub Actions service principal — for Key Vault Secrets User')
param githubActionsPrincipalId string

// ---------------------------------------------------------------------------
// Modules
// ---------------------------------------------------------------------------

module sql 'sql.bicep' = {
  name: 'sql-deploy'
  params: {
    location: location
    environment: environment
    developerObjectId: developerObjectId
  }
}

module aml 'aml.bicep' = {
  name: 'aml-deploy'
  params: {
    location: location
    environment: environment
    storageAccountName: sql.outputs.storageAccountName
    keyVaultName: sql.outputs.keyVaultName
  }
}

module roles 'roles.bicep' = {
  name: 'roles-deploy'
  params: {
    amlWorkspacePrincipalId: aml.outputs.amlWorkspacePrincipalId
    featurePipelineMIPrincipalId: aml.outputs.featurePipelineMIPrincipalId
    storageAccountName: sql.outputs.storageAccountName
    keyVaultName: sql.outputs.keyVaultName
    developerObjectId: developerObjectId
    githubActionsPrincipalId: githubActionsPrincipalId
    environment: environment
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------

output amlWorkspaceName string = aml.outputs.amlWorkspaceName
output featureStoreName string = aml.outputs.featureStoreName
output sqlServerFqdn string = sql.outputs.sqlServerFqdn
output storageAccountName string = sql.outputs.storageAccountName
output keyVaultName string = sql.outputs.keyVaultName
output featurePipelineMIClientId string = aml.outputs.featurePipelineMIClientId
output featurePipelineMIPrincipalId string = aml.outputs.featurePipelineMIPrincipalId
