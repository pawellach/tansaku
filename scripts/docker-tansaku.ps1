[CmdletBinding()]
param(
    [switch]$Build,
    [switch]$Setup,
    [switch]$DryRun,
    [switch]$StartDockerDesktop,
    [string]$ComposeProject = "tansaku"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

function Invoke-Docker([string[]]$Arguments) {
    & docker @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Docker command failed with exit code ${LASTEXITCODE}: docker $($Arguments -join ' ')"
    }
}

function Initialize-ExampleFile([string]$Target, [string]$Example) {
    if (-not (Test-Path -LiteralPath $Target) -and (Test-Path -LiteralPath $Example)) {
        Copy-Item -LiteralPath $Example -Destination $Target
        return $true
    }
    return $false
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker CLI is not on PATH. Start a new PowerShell after installing Docker Desktop."
}

$initialized = @()
if (Initialize-ExampleFile ".env" ".env.example") { $initialized += ".env" }
if (Initialize-ExampleFile "config.yaml" "config.example.yaml") { $initialized += "config.yaml" }
if (Initialize-ExampleFile "team.json" "team.example.json") { $initialized += "team.json" }
if (Initialize-ExampleFile "knowledge-base.json" "knowledge-base.example.json") { $initialized += "knowledge-base.json" }

if ($initialized.Count -gt 0) {
    Write-Host "Initialized missing files: $($initialized -join ', ')"
    throw "Edit .env, config.yaml, team.json, and knowledge-base.json, then run the script again. No Docker command was executed."
}

$dockerReady = $true
try { & docker info *> $null } catch { $dockerReady = $false }
if ($LASTEXITCODE -ne 0) { $dockerReady = $false }

if (-not $dockerReady -and $StartDockerDesktop) {
    $candidates = @(
        "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe",
        "$env:LOCALAPPDATA\Programs\DockerDesktop\Docker Desktop.exe"
    )
    $desktop = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $desktop) { throw "Docker Desktop executable was not found in the standard locations." }
    Start-Process -FilePath $desktop | Out-Null
    Write-Host "Started Docker Desktop; waiting for the engine..."
    $deadline = (Get-Date).AddSeconds(90)
    do {
        Start-Sleep -Seconds 3
        & docker info *> $null
        $dockerReady = ($LASTEXITCODE -eq 0)
    } while (-not $dockerReady -and (Get-Date) -lt $deadline)
}

if (-not $dockerReady) {
    throw "Docker engine is unavailable. Start Docker Desktop, or rerun with -StartDockerDesktop."
}

Invoke-Docker @("compose", "-p", $ComposeProject, "config", "--quiet")
if ($Build) {
    Invoke-Docker @("compose", "-p", $ComposeProject, "build")
}
if ($Setup) {
    Invoke-Docker @("compose", "-p", $ComposeProject, "--profile", "setup", "run", "--rm", "setup")
}

$runCommand = @("compose", "-p", $ComposeProject, "run", "--rm", "tansaku", "tansaku", "run")
if ($DryRun) { $runCommand += "--dry-run" }
Invoke-Docker $runCommand
