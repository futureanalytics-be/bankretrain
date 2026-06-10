// =============================================================================
// BankRetain — AI Resource Group
// bankretain-ai-rg
// Deploys: Azure AI Foundry hub, Foundry project, Azure AI Search, Key Vault
// Region: Sweden Central
// =============================================================================

targetScope = 'resourceGroup'

@description('Environment tag (dev | prod)')
param environment string = 'dev'

@description('Azure region for all resources')
param location string = 'switzerlandnorth'

@description('Principal ID of the feature pipeline MI (from bankretain-ml-rg output) — needs Search Index Data Contributor')
param featurePipelineMIPrincipalId string

@description('Object ID of the developer Entra ID user — for Key Vault Administrator in dev')
param developerObjectId string = ''

@description('Object ID of the GitHub Actions service principal')
param githubActionsPrincipalId string

// ---------------------------------------------------------------------------
// Modules
// ---------------------------------------------------------------------------

module foundry 'foundry.bicep' = {
  name: 'foundry-deploy'
  params: {
    location: location
    environment: environment
  }
}

module aiservices 'aiservices.bicep' = {
  name: 'aiservices-deploy'
  params: {
    location: location
    environment: environment
    foundryHubName: foundry.outputs.foundryHubName
  }
}

module search 'search.bicep' = {
  name: 'search-deploy'
  params: {
    location: location
    environment: environment
  }
}

module roles 'roles.bicep' = {
  name: 'ai-roles-deploy'
  params: {
    foundryProjectPrincipalId: foundry.outputs.foundryProjectPrincipalId
    featurePipelineMIPrincipalId: featurePipelineMIPrincipalId
    searchServiceName: search.outputs.searchServiceName
    keyVaultName: foundry.outputs.keyVaultName
    developerObjectId: developerObjectId
    githubActionsPrincipalId: githubActionsPrincipalId
    environment: environment
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------

output foundryHubName string = foundry.outputs.foundryHubName
output foundryProjectName string = foundry.outputs.foundryProjectName
output foundryProjectPrincipalId string = foundry.outputs.foundryProjectPrincipalId
output searchServiceName string = search.outputs.searchServiceName
output searchServiceEndpoint string = search.outputs.searchServiceEndpoint
output keyVaultName string = foundry.outputs.keyVaultName
output aiServicesName string = aiservices.outputs.aiServicesName
output aiServicesEndpoint string = aiservices.outputs.aiServicesEndpoint
// Project endpoint for pipeline.py and azure-ai-projects SDK
// e.g. https://bankretain-ai-svc-dev-jrkvoy.services.ai.azure.com/api/projects/bankretain-agents-dev
output projectEndpoint string = aiservices.outputs.projectEndpoint
