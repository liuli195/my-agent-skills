import subprocess
import sys
import os
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
VERIFY_INSTALL = REPO_ROOT / "scripts" / "install" / "verify_install.py"
INSTALL_USER_SKILL = REPO_ROOT / "scripts" / "install" / "install_user_skill.ps1"
SYNC_CLAUDE_JUNCTION = REPO_ROOT / "scripts" / "install" / "sync_claude_junction.ps1"
SOURCE_SKILL = REPO_ROOT / ".agents" / "skills" / "agent-guard"
POWERSHELL = "powershell"


def skill_description(skill_path: Path) -> str:
    text = (skill_path / "SKILL.md").read_text(encoding="utf-8")
    lines = text.splitlines()
    in_frontmatter = False
    for line in lines:
        if line.strip() == "---":
            if not in_frontmatter:
                in_frontmatter = True
                continue
            break
        if in_frontmatter and line.startswith("description:"):
            return line.removeprefix("description:").strip()
    raise AssertionError("SKILL.md missing frontmatter description")


def run_verify(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VERIFY_INSTALL), *args],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def run_powershell(script: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    if sys.platform != "win32":
        pytest.skip("PowerShell install scripts are Windows-only")
    return subprocess.run(
        [POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), *args],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_agent_guard_skill_description_covers_guarded_target_types() -> None:
    description = skill_description(SOURCE_SKILL)

    for term in [
        "Skill（技能）",
        "workflow（工作流）",
        "node（节点）",
        "command（命令）",
        "artifact lifecycle（产物生命周期）",
        "Codex lifecycle behavior（Codex 生命周期行为）",
        "PR review order（PR 审查顺序）",
        "Hook enforcement（钩子强制执行）",
        "Guard Injection（守卫注入）",
        "Guard Brief（守卫简报）",
        "Guard Runtime（守卫运行时）",
        "Guard Profile（守卫画像）",
    ]:
        assert term in description


def test_verify_install_reports_complete_source_skeleton(tmp_path: Path) -> None:
    user_skill = tmp_path / "user" / ".agents" / "skills" / "agent-guard"
    claude_skill = tmp_path / "user" / ".claude" / "skills" / "agent-guard"

    result = run_verify(
        [
            "--source-skill",
            str(SOURCE_SKILL),
            "--user-skill",
            str(user_skill),
            "--claude-skill",
            str(claude_skill),
        ]
    )

    assert result.returncode == 1, result.stdout + result.stderr
    assert "source_skill: complete" in result.stdout
    assert "user_skill: missing" in result.stdout
    assert "claude_junction: missing" in result.stdout
    assert "project_guard_initialization: not_performed" in result.stdout
    assert "project_hooks: not_installed" in result.stdout


def test_install_user_skill_defaults_to_dry_run_without_writing_user_skill(tmp_path: Path) -> None:
    user_skill = tmp_path / "user" / ".agents" / "skills" / "agent-guard"

    result = run_powershell(
        INSTALL_USER_SKILL,
        ["-SourceSkill", str(SOURCE_SKILL), "-UserSkill", str(user_skill)],
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: dry_run" in result.stdout
    assert "authorization: missing" in result.stdout
    assert "source_status: complete" in result.stdout
    assert "action: would_sync" in result.stdout
    assert "missing: none" in result.stdout
    assert "conflicts: none" in result.stdout
    assert "expected_result: user_skill_synced" in result.stdout
    assert "project_guard_initialization: not_performed" in result.stdout
    assert "project_hooks: not_installed" in result.stdout
    assert not user_skill.exists()


def test_authorized_user_skill_install_is_repeatable_without_deleting_existing_files(tmp_path: Path) -> None:
    user_skill = tmp_path / "user" / ".agents" / "skills" / "agent-guard"

    first = run_powershell(
        INSTALL_USER_SKILL,
        ["-SourceSkill", str(SOURCE_SKILL), "-UserSkill", str(user_skill), "-AuthorizeInstall"],
    )
    assert first.returncode == 0, first.stdout + first.stderr
    assert "status: installed" in first.stdout
    assert (user_skill / "SKILL.md").exists()
    assert (user_skill / "references").is_dir()
    assert (user_skill / "assets").is_dir()
    assert (user_skill / "scripts").is_dir()

    marker = user_skill / "manual-note.txt"
    marker.write_text("keep me\n", encoding="utf-8")

    second = run_powershell(
        INSTALL_USER_SKILL,
        ["-SourceSkill", str(SOURCE_SKILL), "-UserSkill", str(user_skill), "-AuthorizeInstall"],
    )

    assert second.returncode == 0, second.stdout + second.stderr
    assert "status: installed" in second.stdout
    assert marker.read_text(encoding="utf-8") == "keep me\n"
    assert (user_skill / "SKILL.md").exists()


def test_sync_claude_junction_defaults_to_dry_run_without_creating_junction(tmp_path: Path) -> None:
    user_skill = tmp_path / "user" / ".agents" / "skills" / "agent-guard"
    claude_skill = tmp_path / "user" / ".claude" / "skills" / "agent-guard"
    user_skill.mkdir(parents=True)

    result = run_powershell(
        SYNC_CLAUDE_JUNCTION,
        ["-UserSkill", str(user_skill), "-ClaudeSkill", str(claude_skill)],
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: dry_run" in result.stdout
    assert "authorization: missing" in result.stdout
    assert "claude_junction: missing" in result.stdout
    assert "action: would_create" in result.stdout
    assert "project_guard_initialization: not_performed" in result.stdout
    assert "project_hooks: not_installed" in result.stdout
    assert not claude_skill.exists()


def test_authorized_install_and_junction_sync_verify_as_complete(tmp_path: Path) -> None:
    user_skill = tmp_path / "user" / ".agents" / "skills" / "agent-guard"
    claude_skill = tmp_path / "user" / ".claude" / "skills" / "agent-guard"

    install = run_powershell(
        INSTALL_USER_SKILL,
        ["-SourceSkill", str(SOURCE_SKILL), "-UserSkill", str(user_skill), "-AuthorizeInstall"],
    )
    assert install.returncode == 0, install.stdout + install.stderr

    sync = run_powershell(
        SYNC_CLAUDE_JUNCTION,
        ["-UserSkill", str(user_skill), "-ClaudeSkill", str(claude_skill), "-AuthorizeSync"],
    )
    assert sync.returncode == 0, sync.stdout + sync.stderr
    assert "status: synced" in sync.stdout
    assert "claude_junction: correct_target" in sync.stdout
    assert "action: created" in sync.stdout
    assert os.path.isjunction(claude_skill)

    verify = run_verify(
        [
            "--source-skill",
            str(SOURCE_SKILL),
            "--user-skill",
            str(user_skill),
            "--claude-skill",
            str(claude_skill),
        ]
    )

    assert verify.returncode == 0, verify.stdout + verify.stderr
    assert "status: verified" in verify.stdout
    assert "source_skill: complete" in verify.stdout
    assert "user_skill: complete" in verify.stdout
    assert "claude_junction: correct_target" in verify.stdout


def test_junction_check_reports_wrong_target_and_dry_run_does_not_refresh_it(tmp_path: Path) -> None:
    user_skill = tmp_path / "user" / ".agents" / "skills" / "agent-guard"
    wrong_skill = tmp_path / "user" / ".agents" / "skills" / "wrong-agent-guard"
    claude_skill = tmp_path / "user" / ".claude" / "skills" / "agent-guard"
    wrong_skill.mkdir(parents=True)

    install = run_powershell(
        INSTALL_USER_SKILL,
        ["-SourceSkill", str(SOURCE_SKILL), "-UserSkill", str(user_skill), "-AuthorizeInstall"],
    )
    assert install.returncode == 0, install.stdout + install.stderr

    create_wrong = run_powershell(
        SYNC_CLAUDE_JUNCTION,
        ["-UserSkill", str(wrong_skill), "-ClaudeSkill", str(claude_skill), "-AuthorizeSync"],
    )
    assert create_wrong.returncode == 0, create_wrong.stdout + create_wrong.stderr
    assert os.path.isjunction(claude_skill)
    assert Path(claude_skill).resolve(strict=True) == wrong_skill.resolve(strict=True)

    verify = run_verify(
        [
            "--source-skill",
            str(SOURCE_SKILL),
            "--user-skill",
            str(user_skill),
            "--claude-skill",
            str(claude_skill),
        ]
    )
    assert verify.returncode == 1, verify.stdout + verify.stderr
    assert "user_skill: complete" in verify.stdout
    assert "claude_junction: wrong_target" in verify.stdout

    dry_run = run_powershell(
        SYNC_CLAUDE_JUNCTION,
        ["-UserSkill", str(user_skill), "-ClaudeSkill", str(claude_skill)],
    )

    assert dry_run.returncode == 0, dry_run.stdout + dry_run.stderr
    assert "status: dry_run" in dry_run.stdout
    assert "claude_junction: wrong_target" in dry_run.stdout
    assert "action: would_refresh" in dry_run.stdout
    assert Path(claude_skill).resolve(strict=True) == wrong_skill.resolve(strict=True)

    refresh = run_powershell(
        SYNC_CLAUDE_JUNCTION,
        ["-UserSkill", str(user_skill), "-ClaudeSkill", str(claude_skill), "-AuthorizeSync"],
    )
    assert refresh.returncode == 0, refresh.stdout + refresh.stderr
    assert "status: synced" in refresh.stdout
    assert "claude_junction: correct_target" in refresh.stdout
    assert "action: refreshed" in refresh.stdout
    assert Path(claude_skill).resolve(strict=True) == user_skill.resolve(strict=True)
