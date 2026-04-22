#!/usr/bin/env pwsh
<#
.SYNOPSIS
  Deploy Ratio AI Container Apps to Azure via Bicep.

.DESCRIPTION
  Deploys infra/main.bicep to create/update Container Apps:
    - ca-ratio-ai-sr-insights  (FastAPI backend)
    - ca-ratio-ai-ui           (React frontend)
  In the existing cae-ratio-ai-dev Container Apps Environment.

  Images must already be pushed to ratioaidev ACR (use build\03_push_to_acr.ps1).

.PARAMETER ResourceGroup
  Azure resource group (default: rg-ratioai-dev).
.PARAMETER AzureOpenAiEndpoint
  Azure OpenAI endpoint URL (required).
.PARAMETER ImageTag
  Docker image tag (default: latest).
.PARAMETER WhatIf
  Preview the deployment without making changes.

.EXAMPLE
  .\infra\deploy.ps1 -AzureOpenAiEndpoint "https://myoai.openai.azure.com"
  .\infra\deploy.ps1 -AzureOpenAiEndpoint "https://myoai.openai.azure.com" -ImageTag "20260316-143000"
  .\infra\deploy.ps1 -AzureOpenAiEndpoint "https://myoai.openai.azure.com" -WhatIf
#>
param(
    [string]$ResourceGroup = "rg-ratio-ai-dev",
    [Parameter(Mandatory)][string]$AzureOpenAiEndpoint,
    [string]$ImageTag = "latest",
    [string]$ContainerEnvName = "cae-ratio-ai-dev",
    [string]$AcrName = "ratioaidev",
    [string]$Location = "centralus",
    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"
$infraDir = $PSScriptRoot  # infra/ folder

Write-Host "`n======================================" -ForegroundColor Cyan
Write-Host "  Ratio AI -- Azure Deployment" -ForegroundColor Cyan
Write-Host "======================================`n" -ForegroundColor Cyan

# ── Step 1: Prerequisites ────────────────────────────────────
Write-Host "Step 1: Checking prerequisites..." -ForegroundColor Green
try {
    $account = az account show --query '{name:name, id:id}' -o json 2>$null | ConvertFrom-Json
    Write-Host "  Subscription: $($account.name)" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: Not logged into Azure CLI. Run 'az login' first." -ForegroundColor Red
    exit 1
}

# Check containerapp extension
$extInstalled = az extension list --query "[?name=='containerapp'].name" -o tsv 2>$null
if (-not $extInstalled) {
    Write-Host "  Installing Container Apps extension..." -ForegroundColor Yellow
    az extension add --name containerapp --upgrade --yes
}
Write-Host "  [OK] Prerequisites passed" -ForegroundColor Green
Write-Host ""

# ── Step 2: Verify resource group ────────────────────────────
Write-Host "Step 2: Checking resource group '$ResourceGroup'..." -ForegroundColor Green
$rgExists = az group exists --name $ResourceGroup
if ($rgExists -eq "false") {
    Write-Host "  Resource group '$ResourceGroup' does not exist. Creating..." -ForegroundColor Yellow
    az group create --name $ResourceGroup --location $Location --output none
    if ($LASTEXITCODE -ne 0) { throw "Failed to create resource group" }
}
Write-Host "  [OK] Resource group exists" -ForegroundColor Green
Write-Host ""

# ── Step 3: Verify Container Apps Environment ────────────────
Write-Host "Step 3: Checking Container Apps Environment '$ContainerEnvName'..." -ForegroundColor Green
$ErrorActionPreference = "Continue"
$envExists = az containerapp env show --name $ContainerEnvName --resource-group $ResourceGroup --query name -o tsv 2>$null
$ErrorActionPreference = "Stop"
if (-not $envExists) {
    Write-Host "  Environment '$ContainerEnvName' does not exist. Creating..." -ForegroundColor Yellow
    az containerapp env create --name $ContainerEnvName --resource-group $ResourceGroup --location $Location --output none
    if ($LASTEXITCODE -ne 0) { throw "Failed to create Container Apps Environment" }
    Write-Host "  [OK] Environment created" -ForegroundColor Green
} else {
    Write-Host "  [OK] Environment exists" -ForegroundColor Green
}
Write-Host ""

# ── Step 4: Verify images exist in ACR ───────────────────────
Write-Host "Step 4: Verifying images in ACR '$AcrName'..." -ForegroundColor Green
$ErrorActionPreference = "Continue"
$srTags = az acr repository show-tags --name $AcrName --repository "ratio-sr-insights" --top 3 --orderby time_desc -o tsv 2>$null
$uiTags = az acr repository show-tags --name $AcrName --repository "ratio-ui-web" --top 3 --orderby time_desc -o tsv 2>$null
$ErrorActionPreference = "Stop"

if (-not $srTags) {
    Write-Host "  WARNING: 'ratio-sr-insights' not found in ACR" -ForegroundColor Yellow
    Write-Host "  Run: .\build\03_push_to_acr.ps1 first" -ForegroundColor Yellow
} else {
    Write-Host "  ratio-sr-insights tags: $($srTags -join ', ')" -ForegroundColor Gray
}
if (-not $uiTags) {
    Write-Host "  WARNING: 'ratio-ui-web' not found in ACR" -ForegroundColor Yellow
    Write-Host "  Run: .\build\03_push_to_acr.ps1 first" -ForegroundColor Yellow
} else {
    Write-Host "  ratio-ui-web tags:      $($uiTags -join ', ')" -ForegroundColor Gray
}
Write-Host ""

# ── Step 5: Deploy Bicep ─────────────────────────────────────
$bicepFile = Join-Path $infraDir "main.bicep"
Write-Host "Step 5: Deploying Bicep template..." -ForegroundColor Green
Write-Host "  Template:     $bicepFile" -ForegroundColor Gray
Write-Host "  Resource Group: $ResourceGroup" -ForegroundColor Gray
Write-Host "  Image Tag:    $ImageTag" -ForegroundColor Gray
Write-Host ""

$deployArgs = @(
    "deployment", "group", "create",
    "--resource-group", $ResourceGroup,
    "--template-file", $bicepFile,
    "--parameters",
        "containerEnvName=$ContainerEnvName",
        "acrName=$AcrName",
        "location=$Location",
        "imageTag=$ImageTag",
        "azureOpenAiEndpoint=$AzureOpenAiEndpoint",
    "--output", "json"
)

if ($WhatIf) {
    $deployArgs[2] = "validate"  # validate instead of create
    Write-Host "  [WHAT-IF] Validating only (no changes will be made)..." -ForegroundColor Yellow
}

$result = az @deployArgs | ConvertFrom-Json

if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR: Bicep deployment failed" -ForegroundColor Red
    exit 1
}

if ($WhatIf) {
    Write-Host "  [OK] Template validated successfully" -ForegroundColor Green
    Write-Host "  Run without -WhatIf to deploy." -ForegroundColor Yellow
    exit 0
}

$srInsightsUrl = $result.properties.outputs.srInsightsUrl.value
$uiUrl = $result.properties.outputs.uiUrl.value
$principalId = $result.properties.outputs.srInsightsPrincipalId.value

Write-Host "  [OK] Deployment succeeded" -ForegroundColor Green
Write-Host ""

# ── Step 6: Health check ─────────────────────────────────────
Write-Host "Step 6: Testing deployment..." -ForegroundColor Green
Start-Sleep -Seconds 10

if ($srInsightsUrl) {
    try {
        $healthUrl = "$srInsightsUrl/health"
        $resp = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 15 -ErrorAction SilentlyContinue
        Write-Host "  [OK] SR Insights healthy: $($resp | ConvertTo-Json -Compress)" -ForegroundColor Green
    } catch {
        Write-Host "  WARNING: SR Insights health check failed (may still be starting)" -ForegroundColor Yellow
        Write-Host "  Check logs: az containerapp logs show --name ca-ratio-ai-sr-insights --resource-group $ResourceGroup --follow" -ForegroundColor Gray
    }
}

if ($uiUrl) {
    try {
        $resp = Invoke-WebRequest -Uri $uiUrl -UseBasicParsing -TimeoutSec 10 -ErrorAction SilentlyContinue
        if ($resp.StatusCode -eq 200) {
            Write-Host "  [OK] React UI is serving" -ForegroundColor Green
        }
    } catch {
        Write-Host "  WARNING: UI health check failed (may still be starting)" -ForegroundColor Yellow
    }
}
Write-Host ""

# ── Done ─────────────────────────────────────────────────────
Write-Host "======================================" -ForegroundColor Green
Write-Host "  Deployment Complete!" -ForegroundColor Green
Write-Host "======================================" -ForegroundColor Green
Write-Host ""
Write-Host "  React UI:         $uiUrl" -ForegroundColor White
Write-Host "  SR Insights API:  $srInsightsUrl" -ForegroundColor White
Write-Host "  SR Insights Docs: $srInsightsUrl/docs" -ForegroundColor White
Write-Host "  Managed Identity: $principalId" -ForegroundColor Gray
Write-Host ""
Write-Host "Post-deploy:" -ForegroundColor Yellow
Write-Host "  1. Grant Managed Identity '$principalId' Viewer role on Kusto clusters" -ForegroundColor Gray
Write-Host "  2. Browse the React UI at the URL above" -ForegroundColor Gray
Write-Host ""
Write-Host "Useful commands:" -ForegroundColor Cyan
Write-Host "  Logs:     az containerapp logs show --name ca-ratio-ai-sr-insights --resource-group $ResourceGroup --follow" -ForegroundColor Gray
Write-Host "  Details:  az containerapp show --name ca-ratio-ai-sr-insights --resource-group $ResourceGroup" -ForegroundColor Gray
Write-Host "  Revisions: az containerapp revision list --name ca-ratio-ai-sr-insights --resource-group $ResourceGroup -o table" -ForegroundColor Gray
Write-Host ""
