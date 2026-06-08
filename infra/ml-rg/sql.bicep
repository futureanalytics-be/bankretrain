targetScope = 'resourceGroup'

param location string
param environment string
param sqlAdminLogin string

@secure()
param sqlAdminPassword string

var suffix = uniqueString(resourceGroup().id)
var sqlServerName = 'bankretain-sql-${environment}-${suffix}'
var sqlDbName = 'bankretaindb'
var storageAccountName = 'bankretainst${environment}${take(suffix, 8)}'
var keyVaultName = 'bankretain-kv-ml-${take(suffix, 8)}'

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    networkAcls: {
      defaultAction: 'Allow' // tighten in production
    }
  }
  tags: {
    project: 'bankretain'
    environment: environment
    layer: 'ml'
  }
}

resource sqlServer 'Microsoft.Sql/servers@2023-02-01-preview' = {
  name: sqlServerName
  location: location
  properties: {
    administratorLogin: sqlAdminLogin
    administratorLoginPassword: sqlAdminPassword
    version: '12.0'
    minimalTlsVersion: '1.2'
    publicNetworkAccess: 'Enabled' // set to Disabled + private endpoint in production
  }
  tags: {
    project: 'bankretain'
    environment: environment
    layer: 'ml'
  }
}

// Allow Azure services (Azure ML pipelines, GitHub Actions) to reach SQL
resource sqlFirewallAzureServices 'Microsoft.Sql/servers/firewallRules@2023-02-01-preview' = {
  parent: sqlServer
  name: 'AllowAzureServices'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

resource sqlDatabase 'Microsoft.Sql/servers/databases@2023-02-01-preview' = {
  parent: sqlServer
  name: sqlDbName
  location: location
  sku: {
    name: 'GP_S_Gen5_1'
    tier: 'GeneralPurpose'
  }
  properties: {
    collation: 'SQL_Latin1_General_CP1_CI_AS'
    requestedBackupStorageRedundancy: 'Local'
    useFreeLimit: true
    freeLimitExhaustionBehavior: 'AutoPause'
  }
  tags: {
    project: 'bankretain'
    environment: environment
  }
}

// ---------------------------------------------------------------------------
// Key Vault — stores SQL connection string for ML layer
// ---------------------------------------------------------------------------

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true // RBAC mode — no access policies
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    enabledForDeployment: false
    enabledForDiskEncryption: false
    enabledForTemplateDeployment: true
    publicNetworkAccess: 'Enabled'
  }
  tags: {
    project: 'bankretain'
    environment: environment
    layer: 'ml'
  }
}

// Store SQL connection string as a Key Vault secret
resource sqlConnectionStringSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'sql-connection-string'
  properties: {
    value: 'Server=tcp:${sqlServer.properties.fullyQualifiedDomainName},1433;Initial Catalog=${sqlDbName};Persist Security Info=False;User ID=${sqlAdminLogin};Password=${sqlAdminPassword};MultipleActiveResultSets=False;Encrypt=True;TrustServerCertificate=False;Connection Timeout=30;'
    contentType: 'text/plain'
  }
}

// ---------------------------------------------------------------------------
// Outputs consumed by main.bicep and roles.bicep
// ---------------------------------------------------------------------------

output sqlServerName string = sqlServer.name
output sqlServerFqdn string = sqlServer.properties.fullyQualifiedDomainName
output sqlDatabaseName string = sqlDatabase.name
output storageAccountName string = storageAccount.name
output storageAccountId string = storageAccount.id
output keyVaultName string = keyVault.name
output keyVaultId string = keyVault.id
