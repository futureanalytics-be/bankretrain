// =============================================================================
// BankRetain — Azure AI Services Module
// Deploys: Azure AI Services account (kind=AIServices) with GPT-4o deployment,
//          Foundry project (bankretain-agents-dev), and hub connection.
//
// This provides:
//   - The `services.ai.azure.com` project endpoint for the agent pipeline
//   - GPT-4o model for Agent 1, 2, 3
//   - File search and Foundry Agents capabilities
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
var connectionName = 'bankretain-gpt4o-connection'

// GPT-4o capacity (TPM in thousands). 10k TPM covers the weekly batch pipeline.
var gpt4oCapacity  = 10

// ---------------------------------------------------------------------------
// Azure AI Services account
// Kind = AIServices gives access to Agent Service + file search + GPT-4o.
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
// GPT-4o deployment
// ---------------------------------------------------------------------------

resource gpt4oDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-04-01-preview' = {
  parent: aiServices
  name: 'gpt-4o'
  sku: {
    name: 'GlobalStandard'
    capacity: gpt4oCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-4o'
      version: '2024-11-20'
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
  dependsOn: [gpt4oDeployment]
}

// ---------------------------------------------------------------------------
// Hub connection — wires the AI Services account into the Foundry hub
// so the (legacy) hub/project can also see the GPT-4o deployment.
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
  dependsOn: [gpt4oDeployment]
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------

output aiServicesName        string = aiServices.name
output aiServicesEndpoint    string = aiServices.properties.endpoint
output aiServicesPrincipalId string = aiServices.identity.principalId
output projectName           string = foundryProject.name
// Project endpoint for pipeline.py --ai-services-endpoint and azure-ai-projects SDK
output projectEndpoint       string = 'https://${aiServicesName}.services.ai.azure.com/api/projects/${projectName}'
output projectEndpointBase   string = 'https://${aiServicesName}.services.ai.azure.com'
