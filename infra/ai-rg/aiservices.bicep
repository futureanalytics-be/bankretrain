// =============================================================================
// BankRetain — Azure AI Services Module
// Deploys: Azure AI Services account (kind=AIServices, swedencentral),
//          gpt-4.1 model deployment, Foundry project, and hub connection.
//
// Location: swedencentral — switzerlandnorth has 0 GlobalStandard quota for
// gpt-4.1. The AI Services account is cross-region from the rest of the
// infrastructure; the Foundry hub connection bridges them.
// =============================================================================

targetScope = 'resourceGroup'

param location string
param environment string
param foundryHubName string

// ---------------------------------------------------------------------------
// Naming
// ---------------------------------------------------------------------------

var suffix         = uniqueString(resourceGroup().id)
var aiServicesName = 'bankretain-ai-svc-${environment}-${take(suffix, 6)}'
var projectName    = 'bankretain-agents-${environment}'
var connectionName = 'bankretain-aiservices-connection'

// gpt-4o-mini capacity (TPM in thousands). 10k TPM covers the weekly batch pipeline.
var gpt4oMiniCapacity = 10

// ---------------------------------------------------------------------------
// Azure AI Services account
// Kind = AIServices gives access to Agent Service + file search + gpt-4.1.
// allowProjectManagement = true enables Foundry project creation on this account.
// ---------------------------------------------------------------------------

resource aiServices 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' = {
  name: aiServicesName
  location: location
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    publicNetworkAccess: 'Enabled'
    customSubDomainName: aiServicesName
    allowProjectManagement: true
    apiProperties: {}
  }
  tags: {
    project: 'bankretain'
    environment: environment
    layer: 'ai'
    purpose: 'agent-llm'
  }
}

// ---------------------------------------------------------------------------
// gpt-4.1 deployment
// ---------------------------------------------------------------------------

resource gpt4oMiniDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-04-01-preview' = {
  parent: aiServices
  name: 'gpt-4o-mini'
  sku: {
    name: 'GlobalStandard'
    capacity: gpt4oMiniCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-4o-mini'
      version: '2024-07-18'
    }
    versionUpgradeOption: 'OnceCurrentVersionExpired'
  }
}

// ---------------------------------------------------------------------------
// Foundry project — scopes agents and vector stores to this project
// ---------------------------------------------------------------------------

resource foundryProject 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' = {
  parent: aiServices
  name: projectName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    description: 'BankRetain agent pipeline — churn classification, offer selection, compliance review'
  }
  dependsOn: [gpt4oMiniDeployment]
}

// ---------------------------------------------------------------------------
// Hub connection — wires the AI Services account into the Foundry hub
// ---------------------------------------------------------------------------

resource hubConnection 'Microsoft.MachineLearningServices/workspaces/connections@2024-04-01' = {
  name: '${foundryHubName}/${connectionName}'
  properties: {
    category: 'AIServices'
    target: aiServices.properties.endpoint
    authType: 'AAD'
    isSharedToAll: true
    metadata: {
      ApiType: 'Azure'
      ResourceId: aiServices.id
    }
  }
  dependsOn: [gpt4oMiniDeployment]
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------

output aiServicesName        string = aiServices.name
output aiServicesEndpoint    string = aiServices.properties.endpoint
output aiServicesPrincipalId string = aiServices.identity.principalId
output projectName           string = foundryProject.name
output projectEndpoint       string = 'https://${aiServicesName}.services.ai.azure.com/api/projects/${projectName}'
output projectEndpointBase   string = 'https://${aiServicesName}.services.ai.azure.com'
