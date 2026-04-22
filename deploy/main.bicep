// ============================================
// Ratio AI — Azure Container Apps Infrastructure
// ============================================
// Deploys:
//   - Container App: ca-ratio-ai-sr-insights (FastAPI backend)
//   - Container App: ca-ratio-ai-ui (React frontend)
// Into existing:
//   - Resource Group: rg-ratio-ai-dev
//   - Container Apps Environment: cae-ratio-ai-dev
//   - ACR: ratioaidev
// ============================================

// ── Parameters ──────────────────────────────────────────────

@description('Name of the existing Container Apps Environment')
param containerEnvName string = 'cae-ratio-ai-dev'

@description('Name of the existing Azure Container Registry')
param acrName string = 'ratioaidev'

@description('Azure region for resources')
param location string = resourceGroup().location

@description('Docker image tag')
param imageTag string = 'latest'

// -- SR Insights config --

@description('Azure OpenAI endpoint URL')
param azureOpenAiEndpoint string

@description('Azure OpenAI deployment name')
param azureOpenAiDeployment string = 'gpt-4.1'

@description('Azure OpenAI API version')
param azureOpenAiApiVersion string = '2025-04-01-preview'

@description('Kusto cluster URI for outage data')
param kustoClusterUri string = 'https://ratioadxwus3prod.westus3.kusto.windows.net'

@description('Kusto database name')
param kustoDatabase string = 'ratiodata'

@description('Primo Kusto cluster URI for product name lookups')
param kustoPrimoClusterUri string = 'https://primodsshare.westus3.kusto.windows.net'

@description('Primo Kusto database name')
param kustoPrimoDatabase string = 'primosharedbdev'

// ── Variables ───────────────────────────────────────────────

var acrLoginServer = '${acrName}.azurecr.io'
var srInsightsAppName = 'ca-ratio-ai-sr-insights'
var uiAppName = 'ca-ratio-ai-ui'

// ── Existing Resources (references) ─────────────────────────

resource containerEnv 'Microsoft.App/managedEnvironments@2024-03-01' existing = {
  name: containerEnvName
}

resource acr 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' existing = {
  name: acrName
}

// ── SR Insights — FastAPI Container App ─────────────────────

resource srInsightsApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: srInsightsAppName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: containerEnv.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8006
        transport: 'auto'
        allowInsecure: false
      }
      registries: [
        {
          server: acrLoginServer
          username: acr.listCredentials().username
          passwordSecretRef: 'acr-password'
        }
      ]
      secrets: [
        {
          name: 'acr-password'
          value: acr.listCredentials().passwords[0].value
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'ratio-sr-insights'
          image: '${acrLoginServer}/ratio-sr-insights:${imageTag}'
          resources: {
            cpu: json('1.0')
            memory: '2Gi'
          }
          env: [
            {
              name: 'AZURE_OPENAI_ENDPOINT'
              value: azureOpenAiEndpoint
            }
            {
              name: 'AZURE_OPENAI_DEPLOYMENT'
              value: azureOpenAiDeployment
            }
            {
              name: 'AZURE_OPENAI_API_VERSION'
              value: azureOpenAiApiVersion
            }
            {
              name: 'KUSTO_CLUSTER_URI'
              value: kustoClusterUri
            }
            {
              name: 'KUSTO_DATABASE'
              value: kustoDatabase
            }
            {
              name: 'KUSTO_PRIMO_CLUSTER_URI'
              value: kustoPrimoClusterUri
            }
            {
              name: 'KUSTO_PRIMO_DATABASE'
              value: kustoPrimoDatabase
            }
            {
              name: 'ALLOWED_ORIGINS'
              value: 'https://${uiAppName}.${containerEnv.properties.defaultDomain}'
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 10
      }
    }
  }
}

// ── React UI — Container App ────────────────────────────────

resource uiApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: uiAppName
  location: location
  properties: {
    managedEnvironmentId: containerEnv.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8080
        transport: 'auto'
        allowInsecure: false
      }
      registries: [
        {
          server: acrLoginServer
          username: acr.listCredentials().username
          passwordSecretRef: 'acr-password'
        }
      ]
      secrets: [
        {
          name: 'acr-password'
          value: acr.listCredentials().passwords[0].value
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'ratio-ui-web'
          image: '${acrLoginServer}/ratio-ui-web:${imageTag}'
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            {
              name: 'BACKEND_AGENTS_URL'
              value: 'https://ca-ratio-ai-agents.${containerEnv.properties.defaultDomain}'
            }
            {
              name: 'BACKEND_SR_INSIGHTS_URL'
              value: 'https://${srInsightsApp.properties.configuration.ingress.fqdn}'
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 10
      }
    }
  }
}

// ── Outputs ─────────────────────────────────────────────────

output srInsightsFqdn string = srInsightsApp.properties.configuration.ingress.fqdn
output srInsightsUrl string = 'https://${srInsightsApp.properties.configuration.ingress.fqdn}'
output uiFqdn string = uiApp.properties.configuration.ingress.fqdn
output uiUrl string = 'https://${uiApp.properties.configuration.ingress.fqdn}'
output srInsightsPrincipalId string = srInsightsApp.identity.principalId
