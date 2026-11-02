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

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker CLI is not on PATH. Start a new PowerShell after installing Docker Desktop."
}

if (-not (Test-Path -LiteralPath ".env")) {
    throw "Missing .env. Run: Copy-Item .env.example .env, then fill in Jira/AI/Telegram values."
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
