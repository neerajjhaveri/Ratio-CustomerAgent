// Bicep parameters file for Ratio AI Container Apps deployment.
// Targets existing: rg-ratioai-dev / cae-ratio-ai-dev / ratioaidev ACR
using 'main.bicep'

param containerEnvName = 'cae-ratio-ai-dev'
param acrName = 'ratioaidev'
param location = 'centralus'
param imageTag = 'latest'

// Azure OpenAI — REQUIRED: replace with your actual endpoint
param azureOpenAiEndpoint = '<YOUR_AZURE_OPENAI_ENDPOINT>'
param azureOpenAiDeployment = 'gpt-4.1'
param azureOpenAiApiVersion = '2025-04-01-preview'

// Kusto / ADX
param kustoClusterUri = 'https://ratioadxwus3prod.westus3.kusto.windows.net'
param kustoDatabase = 'ratiodata'
param kustoPrimoClusterUri = 'https://primodsshare.westus3.kusto.windows.net'
param kustoPrimoDatabase = 'primosharedbdev'
