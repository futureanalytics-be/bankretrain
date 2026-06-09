// =============================================================================
// BankRetain — Managed Online Endpoint
// Deploys the churn model endpoint. The model deployment (model attachment
// + traffic split) is handled by evaluate.py and promote.py via AML SDK —
// Bicep only provisions the endpoint resource so it exists before CI/CD runs.
// =============================================================================

targetScope = 'resourceGroup'

param amlWorkspaceName string
param location string
param environment string

var endpointName = 'bankretain-churn-endpoint'

// Reference the existing AML workspace
resource amlWorkspace 'Microsoft.MachineLearningServices/workspaces@2024-01-01-preview' existing = {
  name: amlWorkspaceName
}

// ---------------------------------------------------------------------------
// Managed Online Endpoint
// System-assigned identity so the endpoint can read from the model registry
// and write to Application Insights without stored secrets.
// ---------------------------------------------------------------------------

resource onlineEndpoint 'Microsoft.MachineLearningServices/workspaces/onlineEndpoints@2024-01-01-preview' = {
  parent: amlWorkspace
  name: endpointName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    authMode: 'Key'
    description: 'BankRetain churn prediction endpoint — serves real-time scoring for individual customers'
    publicNetworkAccess: 'Enabled'
    traffic: {}   // deployments manage their own traffic split via promote.py
  }
  tags: {
    project: 'bankretain'
    environment: environment
    purpose: 'churn-scoring'
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------

output endpointName string = onlineEndpoint.name
output scoringUri string   = onlineEndpoint.properties.scoringUri
output endpointPrincipalId string = onlineEndpoint.identity.principalId
