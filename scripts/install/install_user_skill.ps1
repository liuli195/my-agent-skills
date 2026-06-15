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
    "references\architecture.md",
    "references\terminology.md",
    "references\template-index.md",
    "assets",
    "scripts",
    "assets\templates\guard-profile\minimal\GUARD-MANIFEST.yaml",
    "scripts\install_agent_guard_plugin.py"
)

$EntrypointSkills = @(
    "agent-guard-install",
    "agent-guard-init",
    "agent-guard-update",
    "agent-guard-run",
    "agent-guard-hooks"
)

$EntrypointRequiredItems = @{
    "agent-guard-install" = @(
        "SKILL.md",
        "references\research-and-extract.md",
        "references\profile-draft.md"
    )
    "agent-guard-init" = @(
        "SKILL.md",
        "references\init-flow.md",
        "references\init-boundaries.md"
    )
    "agent-guard-update" = @(
        "SKILL.md",
        "references\runtime-update.md",
        "references\profile-sync.md"
    )
    "agent-guard-run" = @(
        "SKILL.md",
        "references\activate.md",
        "references\brief.md",
        "references\events.md"
    )
    "agent-guard-hooks" = @(
        "SKILL.md",
        "references\hook-install.md",
        "references\hook-adapter.md",
        "references\hook-results.md"
    )
}

$EntrypointDisallowedResourceDirs = @(
    "assets",
    "scripts"
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

function Get-EntrypointIssues {
    param([string]$SourceRoot)

    $issues = @()
    foreach ($skillName in $EntrypointSkills) {
        $skillDir = Join-Path $SourceRoot $skillName
        foreach ($item in $EntrypointRequiredItems[$skillName]) {
            if (-not (Test-Path -LiteralPath (Join-Path $skillDir $item))) {
                $issues += "$skillName\$item"
            }
        }
        foreach ($sharedDir in $EntrypointDisallowedResourceDirs) {
            if (Test-Path -LiteralPath (Join-Path $skillDir $sharedDir)) {
                $issues += "$skillName\$sharedDir"
            }
        }
    }
    return $issues
}

function Get-Conflicts {
    param([string]$DestinationRoot)

    $conflicts = @()
    foreach ($skillName in (@("agent-guard") + $EntrypointSkills)) {
        $destination = Join-Path $DestinationRoot $skillName
        if ((Test-Path -LiteralPath $destination) -and -not (Test-Path -LiteralPath $destination -PathType Container)) {
            $conflicts += "$skillName`_path_is_file"
        }
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

function Copy-SkillGroup {
    param(
        [string]$SourceRoot,
        [string]$DestinationRoot
    )

    foreach ($skillName in (@("agent-guard") + $EntrypointSkills)) {
        Copy-SkillContents -Source (Join-Path $SourceRoot $skillName) -Destination (Join-Path $DestinationRoot $skillName)
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
$SourceRoot = Split-Path -Parent $SourceSkill
$UserRoot = Split-Path -Parent $UserSkill

if (-not (Test-Path -LiteralPath $SourceSkill -PathType Container)) {
    Write-Output "status: error"
    Write-Output "reason: source_skill_missing"
    Write-Output "source_skill: $SourceSkill"
    Write-Safety
    exit 2
}

$missingItems = @(Get-MissingItems -Source $SourceSkill)
$entrypointIssues = @(Get-EntrypointIssues -SourceRoot $SourceRoot)
$conflicts = @(Get-Conflicts -DestinationRoot $UserRoot)
$sourceStatus = if ($missingItems.Count -eq 0) { "complete" } else { "incomplete" }
$entrypointsStatus = if ($entrypointIssues.Count -eq 0) { "complete" } else { "incomplete" }

if (-not $AuthorizeInstall) {
    Write-Output "status: dry_run"
    Write-Output "authorization: missing"
    Write-Output "source_skill: $SourceSkill"
    Write-Output "user_skill: $UserSkill"
    Write-Output "source_status: $sourceStatus"
    Write-Output "entrypoints_status: $entrypointsStatus"
    Write-Output "action: would_sync"
    Write-List -Name "missing" -Items @($missingItems + $entrypointIssues)
    Write-List -Name "conflicts" -Items $conflicts
    Write-Output "expected_result: user_skill_synced"
    Write-Output "next: rerun with -AuthorizeInstall to copy the user-level Skill"
    Write-Safety
    if ($missingItems.Count -ne 0 -or $entrypointIssues.Count -ne 0 -or $conflicts.Count -ne 0) {
        exit 1
    }
    exit 0
}

if ($missingItems.Count -ne 0 -or $entrypointIssues.Count -ne 0) {
    Write-Output "status: error"
    Write-Output "reason: source_skill_incomplete"
    Write-Output "source_skill: $SourceSkill"
    Write-List -Name "missing" -Items @($missingItems + $entrypointIssues)
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

Copy-SkillGroup -SourceRoot $SourceRoot -DestinationRoot $UserRoot

Write-Output "status: installed"
Write-Output "authorization: provided"
Write-Output "source_skill: $SourceSkill"
Write-Output "user_skill: $UserSkill"
Write-Output "source_status: complete"
Write-Output "entrypoints_status: complete"
Write-Output "action: synced"
Write-Output "expected_result: user_skill_synced"
Write-Safety
exit 0
