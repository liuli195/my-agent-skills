from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "my-spec"
SPEC_OPS = PLUGIN_ROOT / "skills" / "my-spec" / "scripts" / "spec_ops.py"
INSTALL = PLUGIN_ROOT / "scripts" / "install.py"


def run_python(script: Path, *args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *(str(arg) for arg in args)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def requirement(title: str, behavior: str, scenario: str = "正常流程") -> str:
    return f"""### Requirement: {title}

系统 MUST {behavior}。

#### Scenario: {scenario}

- **WHEN** 用户执行操作
- **THEN** 系统返回结果
"""


def main_spec(capability: str, *requirements: str) -> str:
    return f"""# {capability}

## Purpose

描述 {capability} 的外部行为。

## Requirements

{"\n".join(requirements)}"""


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def test_spec_ops_cli_validates_applies_all_delta_operations_and_diffs(tmp_path: Path) -> None:
    specs = tmp_path / "specs"
    delta = tmp_path / "delta"
    preview = tmp_path / "preview"
    write(
        specs / "accounts" / "spec.md",
        main_spec(
            "Accounts",
            requirement("旧登录", "允许登录"),
            requirement("旧导出", "允许导出"),
            requirement("个人资料", "显示姓名"),
        ),
    )
    write(
        delta / "accounts" / "spec.md",
        """# Accounts

## Purpose

描述 Accounts 的外部行为。

## RENAMED Requirements

FROM: 旧登录
TO: 密码登录

## REMOVED Requirements

### Requirement: 旧导出

## MODIFIED Requirements

### Requirement: 个人资料

系统 SHALL 显示姓名和头像。

#### Scenario: 查看资料

- **WHEN** 用户打开个人资料
- **THEN** 系统显示姓名和头像

## ADDED Requirements

### Requirement: 注销

系统 MUST 允许用户注销。

#### Scenario: 主动注销

- **WHEN** 用户选择注销
- **THEN** 系统结束会话
""",
    )

    assert run_python(SPEC_OPS, "validate-main", specs).returncode == 0
    assert run_python(SPEC_OPS, "validate-delta", delta, specs).returncode == 0
    applied = run_python(SPEC_OPS, "apply-delta", specs, delta, preview)
    assert applied.returncode == 0, applied.stderr
    assert run_python(SPEC_OPS, "validate-main", preview).returncode == 0

    merged = (preview / "accounts" / "spec.md").read_text(encoding="utf-8")
    assert "### Requirement: 密码登录" in merged
    assert "### Requirement: 旧登录" not in merged
    assert "### Requirement: 旧导出" not in merged
    assert "系统 SHALL 显示姓名和头像。" in merged
    assert "### Requirement: 注销" in merged

    diff = run_python(SPEC_OPS, "diff", specs, preview)
    assert diff.returncode == 0
    assert "-### Requirement: 旧登录" in diff.stdout
    assert "+### Requirement: 密码登录" in diff.stdout
    assert "旧导出" in diff.stdout
    assert "注销" in diff.stdout


def test_spec_ops_cli_rejects_invalid_specs_and_delta_references(tmp_path: Path) -> None:
    specs = tmp_path / "specs"
    delta = tmp_path / "delta"
    write(
        specs / "accounts" / "spec.md",
        main_spec("Accounts", requirement("登录", "允许登录").replace("MUST", "必须")),
    )

    invalid_main = run_python(SPEC_OPS, "validate-main", specs)
    assert invalid_main.returncode != 0
    assert "missing_must_or_shall: 登录" in invalid_main.stderr
    assert "Traceback" not in invalid_main.stderr

    write(specs / "accounts" / "spec.md", main_spec("Accounts", requirement("登录", "允许登录")))
    write(
        delta / "accounts" / "spec.md",
        """## REMOVED Requirements

### Requirement: 不存在的需求
""",
    )
    invalid_delta = run_python(SPEC_OPS, "validate-delta", delta, specs)
    assert invalid_delta.returncode != 0
    assert "removed_source_missing: 不存在的需求" in invalid_delta.stderr
    assert "Traceback" not in invalid_delta.stderr


def test_spec_ops_cli_initializes_a_new_capability_from_an_empty_spec_library(tmp_path: Path) -> None:
    specs = tmp_path / "missing-specs"
    delta = tmp_path / "delta"
    preview = tmp_path / "preview"
    write(
        delta / "notifications" / "spec.md",
        """# Notifications

## Purpose

描述通知的外部行为。

## ADDED Requirements

### Requirement: 接收通知

系统 MUST 向订阅用户发送通知。

#### Scenario: 新消息

- **WHEN** 新消息到达
- **THEN** 系统向订阅用户发送通知
""",
    )

    validated = run_python(SPEC_OPS, "validate-delta", delta, specs)
    assert validated.returncode == 0, validated.stderr
    applied = run_python(SPEC_OPS, "apply-delta", specs, delta, preview)
    assert applied.returncode == 0, applied.stderr
    assert run_python(SPEC_OPS, "validate-main", preview).returncode == 0
    assert "### Requirement: 接收通知" in (preview / "notifications" / "spec.md").read_text(encoding="utf-8")


def test_skill_entry_routes_spec_add_review_and_audit_with_safe_boundaries() -> None:
    skill = (PLUGIN_ROOT / "skills" / "my-spec" / "SKILL.md").read_text(encoding="utf-8")
    assert "name: my-spec" in skill
    assert "/spec-add" in skill and "references/add-document.md" in skill
    assert "/spec-review" in skill and "references/review.md" in skill
    assert "/spec-audit" in skill and "references/audit.md" in skill

    add = (PLUGIN_ROOT / "skills" / "my-spec" / "references" / "add-document.md").read_text(encoding="utf-8")
    review = (PLUGIN_ROOT / "skills" / "my-spec" / "references" / "review.md").read_text(encoding="utf-8")
    audit = (PLUGIN_ROOT / "skills" / "my-spec" / "references" / "audit.md").read_text(encoding="utf-8")
    for procedure in (add, review, audit):
        assert "一次只展示一条" in procedure
        assert "完整差异" in procedure
        assert "最终确认" in procedure
        assert "spec_ops.py" in procedure
    assert "只读取 `openspec/specs/`" in review
    assert "不得读取仓库其他文件" in review
    assert "git ls-files --cached --others --exclude-standard" in audit
    assert "只读取用户指定的文档" in add


def test_install_command_copies_shared_skill_links_claude_and_refuses_unknown_targets(tmp_path: Path) -> None:
    agents_home = tmp_path / "agents"
    claude_home = tmp_path / "claude"

    first = run_python(INSTALL, "--agents-home", agents_home, "--claude-home", claude_home)
    assert first.returncode == 0, first.stderr
    installed = agents_home / "skills" / "my-spec"
    claude_skill = claude_home / "skills" / "my-spec"
    assert installed.is_dir() and not installed.is_symlink()
    assert (installed / "SKILL.md").is_file()
    assert (installed / ".my-spec-install.json").is_file()
    installed_cli = installed / "scripts" / "spec_ops.py"
    assert run_python(installed_cli, "validate-main", tmp_path / "empty-specs").returncode == 0
    assert claude_skill.resolve() == installed.resolve()
    assert claude_skill.is_symlink() or (hasattr(claude_skill, "is_junction") and claude_skill.is_junction())

    (installed / "SKILL.md").write_text("stale\n", encoding="utf-8")
    repeated = run_python(INSTALL, "--agents-home", agents_home, "--claude-home", claude_home)
    assert repeated.returncode == 0, repeated.stderr
    assert (installed / "SKILL.md").read_text(encoding="utf-8") != "stale\n"
    assert claude_skill.resolve() == installed.resolve()

    unsafe_agents = tmp_path / "unsafe-agents"
    unsafe_claude = tmp_path / "unsafe-claude"
    unknown = unsafe_claude / "skills" / "my-spec"
    unknown.mkdir(parents=True)
    (unknown / "user.txt").write_text("keep\n", encoding="utf-8")
    refused = run_python(INSTALL, "--agents-home", unsafe_agents, "--claude-home", unsafe_claude)
    assert refused.returncode != 0
    assert "claude_target_not_expected_link" in refused.stderr
    assert (unknown / "user.txt").read_text(encoding="utf-8") == "keep\n"
    assert not (unsafe_agents / "skills" / "my-spec").exists()


def test_my_spec_plugin_is_discoverable_by_claude_and_codex() -> None:
    for host in (".claude-plugin", ".codex-plugin"):
        manifest = json.loads((PLUGIN_ROOT / host / "plugin.json").read_text(encoding="utf-8"))
        assert manifest["name"] == "my-spec"
        assert manifest["skills"] == "./skills"

    claude_marketplace = json.loads((REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    codex_marketplace = json.loads((REPO_ROOT / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8"))
    assert any(plugin["name"] == "my-spec" for plugin in claude_marketplace["plugins"])
    assert any(plugin["name"] == "my-spec" for plugin in codex_marketplace["plugins"])


def test_apply_delta_can_atomically_replace_main_after_final_confirmation(tmp_path: Path) -> None:
    specs = tmp_path / "openspec" / "specs"
    delta = tmp_path / "delta"
    write(specs / "accounts" / "spec.md", main_spec("Accounts", requirement("登录", "允许登录")))
    write(
        delta / "accounts" / "spec.md",
        """## MODIFIED Requirements

### Requirement: 登录

系统 MUST 允许密码登录。

#### Scenario: 密码正确

- **WHEN** 用户提交正确密码
- **THEN** 系统创建会话
""",
    )

    applied = run_python(SPEC_OPS, "apply-delta", specs, delta, specs)
    assert applied.returncode == 0, applied.stderr
    assert "系统 MUST 允许密码登录。" in (specs / "accounts" / "spec.md").read_text(encoding="utf-8")
    assert not any(path.name.startswith(".my-spec-") for path in specs.parent.iterdir())
    assert run_python(SPEC_OPS, "validate-main", specs).returncode == 0

    empty_delta = tmp_path / "empty-delta"
    empty_delta.mkdir()
    before = (specs / "accounts" / "spec.md").read_bytes()
    repeated = run_python(SPEC_OPS, "apply-delta", specs, empty_delta, specs)
    assert repeated.returncode == 0, repeated.stderr
    assert (specs / "accounts" / "spec.md").read_bytes() == before
