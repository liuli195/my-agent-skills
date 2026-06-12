param(
    [string]$UserSkill = "",
    [string]$ClaudeSkill = "",
    [switch]$AuthorizeSync
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

function Resolve-DefaultUserSkill {
    return Join-Path $HOME ".agents\skills\agent-guard"
}

function Resolve-DefaultClaudeSkill {
    return Join-Path $HOME ".claude\skills\agent-guard"
}

function Normalize-PathText {
    param([string]$PathText)
    return [System.IO.Path]::GetFullPath($PathText)
}

function Same-Path {
    param(
        [string]$Left,
        [string]$Right
    )
    return [string]::Equals(
        (Normalize-PathText $Left).TrimEnd('\'),
        (Normalize-PathText $Right).TrimEnd('\'),
        [System.StringComparison]::OrdinalIgnoreCase
    )
}

function Write-Safety {
    Write-Output "safety:"
    Write-Output "  project_guard_initialization: not_performed"
    Write-Output "  project_hooks: not_installed"
    Write-Output "  blocking_mode: not_enabled"
}

function Get-LinkTarget {
    param([System.IO.FileSystemInfo]$Item)
    $target = $Item.Target
    if ($target -is [array]) {
        return [string]$target[0]
    }
    if ($null -eq $target) {
        return ""
    }
    return [string]$target
}

function Get-JunctionState {
    param(
        [string]$Path,
        [string]$ExpectedTarget
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return [pscustomobject]@{
            Status = "missing"
            ActualTarget = ""
            Action = "would_create"
            Writable = $true
        }
    }

    $item = Get-Item -LiteralPath $Path -Force
    if (-not $item.PSIsContainer) {
        return [pscustomobject]@{
            Status = "not_directory"
            ActualTarget = ""
            Action = "conflict"
            Writable = $false
        }
    }

    if ($item.LinkType -ne "Junction") {
        return [pscustomobject]@{
            Status = "not_junction"
            ActualTarget = $item.FullName
            Action = "conflict"
            Writable = $false
        }
    }

    $actualTarget = Get-LinkTarget -Item $item
    if (Same-Path $actualTarget $ExpectedTarget) {
        return [pscustomobject]@{
            Status = "correct_target"
            ActualTarget = (Normalize-PathText $actualTarget)
            Action = "none"
            Writable = $true
        }
    }

    return [pscustomobject]@{
        Status = "wrong_target"
        ActualTarget = (Normalize-PathText $actualTarget)
        Action = "would_refresh"
        Writable = $true
    }
}

function Write-State {
    param(
        [string]$Status,
        [string]$Authorization,
        [string]$UserSkillPath,
        [string]$ClaudeSkillPath,
        [object]$State,
        [string]$Action
    )

    Write-Output "status: $Status"
    Write-Output "authorization: $Authorization"
    Write-Output "user_skill: $UserSkillPath"
    Write-Output "claude_skill: $ClaudeSkillPath"
    Write-Output "claude_junction: $($State.Status)"
    Write-Output "expected_target: $UserSkillPath"
    if (-not [string]::IsNullOrWhiteSpace($State.ActualTarget)) {
        Write-Output "actual_target: $($State.ActualTarget)"
    }
    Write-Output "action: $Action"
    Write-Safety
}

if ([string]::IsNullOrWhiteSpace($UserSkill)) {
    $UserSkill = Resolve-DefaultUserSkill
}
if ([string]::IsNullOrWhiteSpace($ClaudeSkill)) {
    $ClaudeSkill = Resolve-DefaultClaudeSkill
}

$UserSkill = Normalize-PathText $UserSkill
$ClaudeSkill = Normalize-PathText $ClaudeSkill

if (-not (Test-Path -LiteralPath $UserSkill -PathType Container)) {
    Write-Output "status: error"
    Write-Output "reason: user_skill_missing"
    Write-Output "user_skill: $UserSkill"
    Write-Safety
    exit 2
}

$state = Get-JunctionState -Path $ClaudeSkill -ExpectedTarget $UserSkill

if (-not $AuthorizeSync) {
    Write-State -Status "dry_run" -Authorization "missing" -UserSkillPath $UserSkill -ClaudeSkillPath $ClaudeSkill -State $state -Action $state.Action
    exit 0
}

if (-not $state.Writable) {
    Write-State -Status "conflict" -Authorization "provided" -UserSkillPath $UserSkill -ClaudeSkillPath $ClaudeSkill -State $state -Action "manual_resolution_required"
    exit 1
}

$performedAction = "already_correct"
if ($state.Status -eq "missing") {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $ClaudeSkill) | Out-Null
    New-Item -ItemType Junction -Path $ClaudeSkill -Target $UserSkill | Out-Null
    $performedAction = "created"
} elseif ($state.Status -eq "wrong_target") {
    Remove-Item -LiteralPath $ClaudeSkill -Force
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $ClaudeSkill) | Out-Null
    New-Item -ItemType Junction -Path $ClaudeSkill -Target $UserSkill | Out-Null
    $performedAction = "refreshed"
}

$updatedState = Get-JunctionState -Path $ClaudeSkill -ExpectedTarget $UserSkill
Write-State -Status "synced" -Authorization "provided" -UserSkillPath $UserSkill -ClaudeSkillPath $ClaudeSkill -State $updatedState -Action $performedAction
exit 0
