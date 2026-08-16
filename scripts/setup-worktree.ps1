[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
$pythonManifests = @('requirements-dev.txt')
$nodeManifests = @('package.json', 'package-lock.json')

function Get-FileSha256([string]$path) {
    $text = [IO.File]::ReadAllText($path).Replace("`r`n", "`n")
    $sha256 = [Security.Cryptography.SHA256]::Create()
    try {
        return [BitConverter]::ToString($sha256.ComputeHash([Text.Encoding]::UTF8.GetBytes($text))).Replace('-', '')
    }
    finally {
        $sha256.Dispose()
    }
}

function Get-DependencyFingerprint([string]$root, [string[]]$manifests) {
    foreach ($manifest in $manifests) {
        "$(Get-FileSha256 (Join-Path $root $manifest)) $manifest"
    }
}

function Assert-MatchingManifests([string[]]$manifests, [string]$sharedRoot) {
    foreach ($manifest in $manifests) {
        $localManifest = Join-Path $projectRoot $manifest
        $sharedManifest = Join-Path $sharedRoot $manifest
        if (-not (Test-Path $sharedManifest) -or
            (Get-FileSha256 $localManifest) -ne (Get-FileSha256 $sharedManifest)) {
            throw "Shared dependencies do not match '$manifest'. Initialize them from '$sharedRoot'."
        }
    }
}

function Assert-LinkOrMissing([string]$path, [string]$target) {
    if (-not (Test-Path $path)) { return }
    $link = Get-Item $path
    $actualTarget = if ($link.Target) {
        $rawTarget = [string]$link.Target
        if ([IO.Path]::IsPathRooted($rawTarget)) {
            [IO.Path]::GetFullPath($rawTarget)
        }
        else {
            [IO.Path]::GetFullPath((Join-Path $projectRoot $rawTarget))
        }
    }
    else { '' }
    $expectedTarget = [IO.Path]::GetFullPath($target)
    if (-not ($link.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
        -not $actualTarget.Equals($expectedTarget, [StringComparison]::OrdinalIgnoreCase)) {
        throw "'$path' already exists and does not link to '$target'."
    }
}

Push-Location $projectRoot
try {
    $gitCommonDir = (& git rev-parse --path-format=absolute --git-common-dir).Trim()
    if ($LASTEXITCODE) { exit $LASTEXITCODE }
    $sharedRoot = Split-Path -Parent $gitCommonDir
    $isMainWorktree = [IO.Path]::GetFullPath($projectRoot) -eq [IO.Path]::GetFullPath($sharedRoot)

    if (-not $isMainWorktree) {
        Assert-MatchingManifests $nodeManifests $sharedRoot
        Assert-MatchingManifests $pythonManifests $sharedRoot

        $sharedNodeModules = Join-Path $sharedRoot 'node_modules'
        if (-not (Test-Path $sharedNodeModules)) {
            throw "Shared Node.js dependencies are missing. Run scripts\setup-worktree.ps1 from '$sharedRoot'."
        }
        $nodeFingerprintPath = Join-Path $sharedNodeModules '.package-lock.sha256'
        if (-not (Test-Path $nodeFingerprintPath) -or
            (Compare-Object (Get-Content $nodeFingerprintPath) (Get-DependencyFingerprint $sharedRoot $nodeManifests))) {
            throw "Shared Node.js dependencies are stale. Run scripts\setup-worktree.ps1 from '$sharedRoot'."
        }

        $sharedVenv = Join-Path $sharedRoot '.venv'
        if (-not (Test-Path (Join-Path $sharedVenv 'Scripts\python.exe'))) {
            throw "Shared Python environment is missing. Run scripts\setup-worktree.ps1 from '$sharedRoot'."
        }
        $fingerprintPath = Join-Path $sharedVenv '.requirements.sha256'
        if (-not (Test-Path $fingerprintPath) -or
            (Compare-Object (Get-Content $fingerprintPath) (Get-DependencyFingerprint $sharedRoot $pythonManifests))) {
            throw "Shared Python environment is stale. Run scripts\setup-worktree.ps1 from '$sharedRoot'."
        }

        $localNodeModules = Join-Path $projectRoot 'node_modules'
        $localVenv = Join-Path $projectRoot '.venv'
        Assert-LinkOrMissing $localNodeModules $sharedNodeModules
        Assert-LinkOrMissing $localVenv $sharedVenv
        if (-not (Test-Path $localNodeModules)) {
            New-Item -ItemType Junction -Path $localNodeModules -Target $sharedNodeModules | Out-Null
        }
        if (-not (Test-Path $localVenv)) {
            New-Item -ItemType Junction -Path $localVenv -Target $sharedVenv | Out-Null
        }
        exit 0
    }

    foreach ($ownedDirectory in @('node_modules', '.venv')) {
        $ownedPath = Join-Path $projectRoot $ownedDirectory
        if ((Test-Path $ownedPath) -and ((Get-Item $ownedPath).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw "Main repository '$ownedPath' must own its dependency directory instead of linking elsewhere."
        }
    }

    npm ci
    if ($LASTEXITCODE) { exit $LASTEXITCODE }
    Get-DependencyFingerprint $projectRoot $nodeManifests | Set-Content (Join-Path $projectRoot 'node_modules\.package-lock.sha256') -Encoding ascii

    if (-not (Test-Path $python)) {
        py -3.12 -m venv .venv
        if ($LASTEXITCODE) { exit $LASTEXITCODE }
    }

    Remove-Item (Join-Path $projectRoot '.venv\.requirements.sha256') -Force -ErrorAction SilentlyContinue
    & $python -m pip install --upgrade pip
    if ($LASTEXITCODE) { exit $LASTEXITCODE }
    & $python -m pip install -r requirements-dev.txt
    if ($LASTEXITCODE) { exit $LASTEXITCODE }
    Get-DependencyFingerprint $projectRoot $pythonManifests | Set-Content (Join-Path $projectRoot '.venv\.requirements.sha256') -Encoding ascii
    exit 0
}
finally {
    Pop-Location
}
