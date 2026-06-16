import subprocess
import sys
import os
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "agent-guard"
VERIFY_INSTALL = REPO_ROOT / "scripts" / "install" / "verify_install.py"
INSTALL_USER_SKILL = REPO_ROOT / "scripts" / "install" / "install_user_skill.ps1"
SYNC_CLAUDE_JUNCTION = REPO_ROOT / "scripts" / "install" / "sync_claude_junction.ps1"
SOURCE_SKILL = PLUGIN_ROOT / "skills" / "agent-guard"
POWERSHELL = "powershell"
ENTRYPOINT_SKILLS = [
    "agent-guard-install",
    "agent-guard-init",
    "agent-guard-update",
    "agent-guard-run",
]
ENTRYPOINT_REFERENCES = {
    "agent-guard-install": ["research-and-extract.md", "profile-draft.md"],
    "agent-guard-init": ["init-flow.md", "init-boundaries.md"],
    "agent-guard-update": ["runtime-update.md", "profile-sync.md"],
    "agent-guard-run": ["activate.md", "brief.md", "events.md", "close.md"],
}


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


def test_agent_guard_router_description_covers_routing_triggers() -> None:
    description = skill_description(SOURCE_SKILL)

    for term in [
        "路由",
        "Use when",
        "agent-guard",
        "install/init/update/run",
    ]:
        assert term in description
    for term in ["Guard Profile（守卫画像）", "Guard Runtime（守卫运行时）", "Hook（钩子）"]:
        assert term not in description


def test_agent_guard_router_points_to_scenario_entrypoints() -> None:
    skill_text = (SOURCE_SKILL / "SKILL.md").read_text(encoding="utf-8")

    assert "薄路由" in skill_text
    for entrypoint in ENTRYPOINT_SKILLS:
        assert f"${entrypoint}" in skill_text
    assert "$agent-guard-hooks" not in skill_text


def test_scenario_entrypoints_have_strong_required_steps() -> None:
    required_phrases = {
        "agent-guard-install": [
            "安装守卫",
            "立即执行：在调研、生成或更新任何 Guard Profile（守卫画像）前，使用 Skill 工具加载 `$grill-with-docs`。禁止跳过此步骤。",
            "references/research-and-extract.md",
            "references/profile-draft.md",
        ],
        "agent-guard-init": [
            "初始化守卫",
            "立即执行：在初始化任何项目级或用户级 Guard Profile（守卫画像）前，运行 `validate_guard_profile.py <guard-profile-dir>`。禁止跳过此步骤。",
            "references/init-flow.md",
            "references/init-boundaries.md",
        ],
        "agent-guard-update": [
            "更新守卫",
            "立即执行：在把更新后的 Guard Profile（守卫画像）同步到已初始化守卫前，运行 `validate_guard_profile.py <guard-profile-dir>`。禁止跳过此步骤。",
            "references/runtime-update.md",
            "references/profile-sync.md",
        ],
        "agent-guard-run": [
            "运行守卫",
            "立即执行：提交任何 `state_completed` 事件前，读取当前 Session Focus Instance（会话焦点实例）的最新 Guard Brief（守卫简报）。禁止跳过此步骤。",
            "references/activate.md",
            "references/brief.md",
            "references/events.md",
            "references/close.md",
        ],
    }

    for entrypoint, phrases in required_phrases.items():
        skill_dir = SOURCE_SKILL.parent / entrypoint
        skill_text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
        description = skill_description(skill_dir)
        assert "Use when" in description
        for phrase in phrases:
            assert phrase in skill_text
        for reference_name in ENTRYPOINT_REFERENCES[entrypoint]:
            assert (skill_dir / "references" / reference_name).exists()
        for shared_dir in ["scripts", "assets"]:
            assert not (skill_dir / shared_dir).exists()


def test_core_references_are_common_and_scenario_docs_live_with_entrypoints() -> None:
    core_references = SOURCE_SKILL / "references"

    for reference_name in [
        "architecture.md",
        "terminology.md",
        "template-index.md",
    ]:
        assert (core_references / reference_name).exists()

    for obsolete_name in [
        "subject-resolution.md",
        "extraction-method.md",
        "guard-profile.md",
        "runtime-contract.md",
        "hook-contract.md",
        "guard-injection.md",
        "codex-claude-compat.md",
    ]:
        assert not (core_references / obsolete_name).exists()

    for entrypoint, reference_names in ENTRYPOINT_REFERENCES.items():
        entrypoint_references = SOURCE_SKILL.parent / entrypoint / "references"
        assert entrypoint_references.is_dir()
        for reference_name in reference_names:
            assert (entrypoint_references / reference_name).exists()


def test_templates_do_not_include_python_cache_artifacts() -> None:
    templates_root = SOURCE_SKILL / "assets" / "templates"

    assert not list(templates_root.rglob("__pycache__"))
    assert not list(templates_root.rglob("*.pyc"))


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
    assert "source_entrypoints: complete" in result.stdout
    assert "user_skill: missing" in result.stdout
    assert "user_entrypoints: missing" in result.stdout
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
    assert "entrypoints_status: complete" in result.stdout
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
    user_skills_root = user_skill.parent
    for entrypoint in ENTRYPOINT_SKILLS:
        entrypoint_dir = user_skills_root / entrypoint
        assert (entrypoint_dir / "SKILL.md").exists()
        assert (entrypoint_dir / "references").is_dir()
        for reference_name in ENTRYPOINT_REFERENCES[entrypoint]:
            assert (entrypoint_dir / "references" / reference_name).exists()
        assert not (entrypoint_dir / "assets").exists()
        assert not (entrypoint_dir / "scripts").exists()

    marker = user_skill / "manual-note.txt"
    marker.write_text("keep me\n", encoding="utf-8")
    entrypoint_marker = user_skills_root / "agent-guard-run" / "manual-note.txt"
    entrypoint_marker.write_text("keep me too\n", encoding="utf-8")

    second = run_powershell(
        INSTALL_USER_SKILL,
        ["-SourceSkill", str(SOURCE_SKILL), "-UserSkill", str(user_skill), "-AuthorizeInstall"],
    )

    assert second.returncode == 0, second.stdout + second.stderr
    assert "status: installed" in second.stdout
    assert marker.read_text(encoding="utf-8") == "keep me\n"
    assert entrypoint_marker.read_text(encoding="utf-8") == "keep me too\n"
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
