[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'

Push-Location $projectRoot
try {
    $gitCommonDir = (& git rev-parse --path-format=absolute --git-common-dir).Trim()
    if ($LASTEXITCODE) { exit $LASTEXITCODE }
    $sharedRoot = Split-Path -Parent $gitCommonDir
    $isMainWorktree = [System.IO.Path]::GetFullPath($projectRoot) -eq [System.IO.Path]::GetFullPath($sharedRoot)

    if ($isMainWorktree) {
        npm ci
        if ($LASTEXITCODE) { exit $LASTEXITCODE }
    }
    else {
        function Get-ManifestHash($path) {
            $text = [IO.File]::ReadAllText($path).Replace("`r`n", "`n")
            $sha256 = [Security.Cryptography.SHA256]::Create()
            try {
                return [BitConverter]::ToString($sha256.ComputeHash([Text.Encoding]::UTF8.GetBytes($text))).Replace('-', '')
            }
            finally {
                $sha256.Dispose()
            }
        }

        foreach ($manifest in @('package.json', 'package-lock.json', 'plugins\pi-tool-display\package.json')) {
            $localManifest = Join-Path $projectRoot $manifest
            $sharedManifest = Join-Path $sharedRoot $manifest
            if (-not (Test-Path $sharedManifest) -or
                (Get-ManifestHash $localManifest) -ne (Get-ManifestHash $sharedManifest)) {
                throw "Shared Node.js dependencies do not match '$manifest'. Initialize them from '$sharedRoot'."
            }
        }

        $sharedNodeModules = Join-Path $sharedRoot 'node_modules'
        $localNodeModules = Join-Path $projectRoot 'node_modules'
        if (-not (Test-Path $sharedNodeModules)) {
            throw "Shared Node.js dependencies are missing. Run scripts\setup-worktree.ps1 from '$sharedRoot'."
        }
        if (-not (Test-Path $localNodeModules)) {
            New-Item -ItemType Junction -Path $localNodeModules -Target $sharedNodeModules | Out-Null
        }
        else {
            $link = Get-Item $localNodeModules
            $actualTarget = if ($link.Target) {
                $target = [string]$link.Target
                [IO.Path]::GetFullPath($(if ([IO.Path]::IsPathRooted($target)) { $target } else { Join-Path $projectRoot $target }))
            } else { '' }
            $expectedTarget = [IO.Path]::GetFullPath($sharedNodeModules)
            if (-not ($link.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
                -not $actualTarget.Equals($expectedTarget, [StringComparison]::OrdinalIgnoreCase)) {
                throw "'$localNodeModules' already exists and does not link to '$sharedNodeModules'."
            }
        }
    }

    if (-not (Test-Path $python)) {
        py -3.12 -m venv .venv
        if ($LASTEXITCODE) { exit $LASTEXITCODE }
    }

    & $python -m pip install --upgrade pip
    if ($LASTEXITCODE) { exit $LASTEXITCODE }

    & $python -m pip install -r requirements-dev.txt
    if ($LASTEXITCODE) { exit $LASTEXITCODE }

    exit 0
}
finally {
    Pop-Location
}
