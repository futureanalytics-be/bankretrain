// =============================================================================
// BankRetain — Azure AI Services Module
// Deploys: Azure AI Services account (kind=AIServices),
//          Foundry project (bankretain-agents-dev), and hub connection.
//
// NOTE — model deployment is NOT managed by Bicep.
// GlobalStandard quota for GPT-4.1 in switzerlandnorth must be requested via
// the Azure Portal (Quotas blade) before deploying a model. After quota is
// approved, run:
//   az cognitiveservices account deployment create \
//     --name <aiServicesName> --resource-group bankretain-ai-rg \
//     --deployment-name gpt-4.1 \
//     --model-name gpt-4.1 --model-version 2025-04-14 --model-format OpenAI \
//     --sku-name GlobalStandard --sku-capacity 10
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

// ---------------------------------------------------------------------------
// Azure AI Services account
// Kind = AIServices gives access to Agent Service + file search + GPT-4.1.
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
