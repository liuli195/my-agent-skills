param(
    [string]$SourceSkill = "",
    [string]$UserSkill = "",
    [switch]$AuthorizeInstall
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$RequiredItems = @(
    "SKILL.md",
    "agents\openai.yaml",
    "references",
    "assets",
    "scripts",
    "assets\templates\guard-runtime\guard_runner.py",
    "assets\templates\guard-runtime\hook_event_adapter.py",
    "assets\templates\guard-profile\minimal\GUARD-MANIFEST.yaml",
    "assets\templates\codex-hooks\hooks.json",
    "assets\templates\git-hooks\pre-push"
)

function Resolve-DefaultSourceSkill {
    $repoRoot = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\..")
    return Join-Path $repoRoot "skills\agent-guard"
}

function Resolve-DefaultUserSkill {
    return Join-Path $HOME ".agents\skills\agent-guard"
}

function Write-Safety {
    Write-Output "safety:"
    Write-Output "  project_guard_initialization: not_performed"
    Write-Output "  project_hooks: not_installed"
}

function Get-MissingItems {
    param([string]$Source)

    $missing = @()
    foreach ($item in $RequiredItems) {
        if (-not (Test-Path -LiteralPath (Join-Path $Source $item))) {
            $missing += $item
        }
    }
    return $missing
}

function Get-Conflicts {
    param([string]$Destination)

    $conflicts = @()
    if ((Test-Path -LiteralPath $Destination) -and -not (Test-Path -LiteralPath $Destination -PathType Container)) {
        $conflicts += "user_skill_path_is_file"
    }
    return $conflicts
}

function Write-List {
    param(
        [string]$Name,
        [string[]]$Items
    )

    if ($Items.Count -eq 0) {
        Write-Output "${Name}: none"
        return
    }

    Write-Output "${Name}:"
    foreach ($item in $Items) {
        Write-Output "  - $item"
    }
}

function Copy-SkillContents {
    param(
        [string]$Source,
        [string]$Destination
    )

    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    Get-ChildItem -LiteralPath $Source -Force | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $Destination -Recurse -Force
    }
}

if ([string]::IsNullOrWhiteSpace($SourceSkill)) {
    $SourceSkill = Resolve-DefaultSourceSkill
}
if ([string]::IsNullOrWhiteSpace($UserSkill)) {
    $UserSkill = Resolve-DefaultUserSkill
}

$SourceSkill = [System.IO.Path]::GetFullPath($SourceSkill)
$UserSkill = [System.IO.Path]::GetFullPath($UserSkill)

if (-not (Test-Path -LiteralPath $SourceSkill -PathType Container)) {
    Write-Output "status: error"
    Write-Output "reason: source_skill_missing"
    Write-Output "source_skill: $SourceSkill"
    Write-Safety
    exit 2
}

$missingItems = @(Get-MissingItems -Source $SourceSkill)
$conflicts = @(Get-Conflicts -Destination $UserSkill)
$sourceStatus = if ($missingItems.Count -eq 0) { "complete" } else { "incomplete" }

if (-not $AuthorizeInstall) {
    Write-Output "status: dry_run"
    Write-Output "authorization: missing"
    Write-Output "source_skill: $SourceSkill"
    Write-Output "user_skill: $UserSkill"
    Write-Output "source_status: $sourceStatus"
    Write-Output "action: would_sync"
    Write-List -Name "missing" -Items $missingItems
    Write-List -Name "conflicts" -Items $conflicts
    Write-Output "expected_result: user_skill_synced"
    Write-Output "next: rerun with -AuthorizeInstall to copy the user-level Skill"
    Write-Safety
    if ($missingItems.Count -ne 0 -or $conflicts.Count -ne 0) {
        exit 1
    }
    exit 0
}

if ($missingItems.Count -ne 0) {
    Write-Output "status: error"
    Write-Output "reason: source_skill_incomplete"
    Write-Output "source_skill: $SourceSkill"
    Write-List -Name "missing" -Items $missingItems
    Write-Safety
    exit 2
}

if ($conflicts.Count -ne 0) {
    Write-Output "status: conflict"
    Write-Output "source_skill: $SourceSkill"
    Write-Output "user_skill: $UserSkill"
    Write-List -Name "conflicts" -Items $conflicts
    Write-Safety
    exit 1
}

Copy-SkillContents -Source $SourceSkill -Destination $UserSkill

Write-Output "status: installed"
Write-Output "authorization: provided"
Write-Output "source_skill: $SourceSkill"
Write-Output "user_skill: $UserSkill"
Write-Output "source_status: complete"
Write-Output "action: synced"
Write-Output "expected_result: user_skill_synced"
Write-Safety
exit 0
