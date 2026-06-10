// =============================================================================
// BankRetain — Azure AI Services Module
// Deploys: Azure AI Services account (kind=AIServices, germanywestcentral),
//          Foundry project, and hub connection.
//
// Location: germanywestcentral — only region allowed by subscription policy
// that also supports AIServices kind.
//
// NOTE: Model deployment is NOT managed here. This subscription has 0
// GlobalStandard quota for all GPT models in all allowed regions. Request a
// quota increase via Azure Portal → Quotas → Azure OpenAI, then deploy the
// model manually or add it back once quota is granted.
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
// Kind = AIServices gives access to Agent Service + file search.
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
// gpt-oss-120b deployment
// Uses AIServices.GlobalStandard quota pool (5000K TPM available) rather than
// OpenAI.GlobalStandard, which has 0 quota on this subscription.
// ---------------------------------------------------------------------------

resource gptOss120bDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-04-01-preview' = {
  parent: aiServices
  name: 'gpt-oss-120b'
  sku: {
    name: 'GlobalStandard'
    capacity: 10
  }
  properties: {
    model: {
      format: 'OpenAI-OSS'
      name: 'gpt-oss-120b'
      version: '1'
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
  dependsOn: [gptOss120bDeployment]
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
