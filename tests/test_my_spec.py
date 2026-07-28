from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "my-spec"
SPEC_OPS = PLUGIN_ROOT / "skills" / "my-spec" / "scripts" / "spec_ops.py"
SKILL_NAMES = ("my-spec", "my-spec-add", "my-spec-review", "my-spec-audit")


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


def run_confirmed_workflow(
    cli: Path,
    specs: Path,
    delta: Path,
    preview: Path,
    *expected_diff: str,
) -> str:
    validated = run_python(cli, "validate-delta", delta, specs)
    assert validated.returncode == 0, validated.stderr
    generated = run_python(cli, "apply-delta", specs, delta, preview)
    assert generated.returncode == 0, generated.stderr
    assert run_python(cli, "validate-main", preview).returncode == 0
    diff = run_python(cli, "diff", specs, preview)
    assert diff.returncode == 0, diff.stderr
    for fragment in expected_diff:
        assert fragment in diff.stdout
    applied = run_python(cli, "apply-delta", specs, delta, specs)
    assert applied.returncode == 0, applied.stderr
    assert run_python(cli, "validate-main", specs).returncode == 0
    assert run_python(cli, "diff", specs, preview).stdout == ""
    return diff.stdout


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

    first_apply = run_python(SPEC_OPS, "apply-delta", specs, delta, specs)
    assert first_apply.returncode == 0, first_apply.stderr
    before_repeat = (specs / "accounts" / "spec.md").read_bytes()
    repeated_validation = run_python(SPEC_OPS, "validate-delta", delta, specs)
    assert repeated_validation.returncode == 0, repeated_validation.stderr
    repeated_apply = run_python(SPEC_OPS, "apply-delta", specs, delta, specs)
    assert repeated_apply.returncode == 0, repeated_apply.stderr
    assert (specs / "accounts" / "spec.md").read_bytes() == before_repeat


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
        """## MODIFIED Requirements

### Requirement: 不存在的需求

系统 MUST 返回结果。

#### Scenario: 正常流程

- **WHEN** 用户执行操作
- **THEN** 系统返回结果
""",
    )
    invalid_delta = run_python(SPEC_OPS, "validate-delta", delta, specs)
    assert invalid_delta.returncode != 0
    assert "modified_source_missing: 不存在的需求" in invalid_delta.stderr
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


def test_spec_ops_preview_auto_merges_identical_duplicate_requirements_but_main_validation_stays_strict(
    tmp_path: Path,
) -> None:
    specs = tmp_path / "specs"
    delta = tmp_path / "delta"
    preview = tmp_path / "preview"
    duplicate = requirement("登录", "允许用户登录")
    write(specs / "accounts" / "spec.md", main_spec("Accounts", duplicate))
    write(specs / "sessions" / "spec.md", main_spec("Sessions", duplicate))
    delta.mkdir()

    strict = run_python(SPEC_OPS, "validate-main", specs)
    assert strict.returncode != 0
    assert "duplicate_requirement_global: 登录" in strict.stderr

    merged = run_python(SPEC_OPS, "apply-delta", specs, delta, preview)
    assert merged.returncode == 0, merged.stderr
    assert run_python(SPEC_OPS, "validate-main", preview).returncode == 0
    assert (preview / "accounts" / "spec.md").read_text(encoding="utf-8").count(
        "### Requirement: 登录"
    ) == 1
    diff = run_python(SPEC_OPS, "diff", specs, preview)
    assert diff.returncode == 0
    assert "-### Requirement: 登录" in diff.stdout


def test_skill_entries_route_add_review_and_audit_with_safe_boundaries() -> None:
    skill = (PLUGIN_ROOT / "skills" / "my-spec" / "SKILL.md").read_text(encoding="utf-8")
    assert "name: my-spec" in skill
    assert "my-spec-add" in skill and "references/add-document.md" in skill
    assert "my-spec-review" in skill and "references/review.md" in skill
    assert "my-spec-audit" in skill and "references/audit.md" in skill

    for name in SKILL_NAMES:
        entry = (PLUGIN_ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
        assert f"name: {name}" in entry
    for name in SKILL_NAMES[1:]:
        entry = (PLUGIN_ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
        assert "../my-spec/SKILL.md" in entry
        assert "../my-spec/scripts/spec_ops.py" in entry

    add = (PLUGIN_ROOT / "skills" / "my-spec" / "references" / "add-document.md").read_text(encoding="utf-8")
    review = (PLUGIN_ROOT / "skills" / "my-spec" / "references" / "review.md").read_text(encoding="utf-8")
    audit = (PLUGIN_ROOT / "skills" / "my-spec" / "references" / "audit.md").read_text(encoding="utf-8")
    rules = (PLUGIN_ROOT / "skills" / "my-spec" / "references" / "openspec-rules.md").read_text(encoding="utf-8")
    for procedure in (add, review, audit):
        assert "一次只展示一条" in procedure
        assert "完整差异" in procedure
        assert "最终确认" in procedure
        assert "spec_ops.py" in procedure
    assert "只读取 `openspec/specs/`" in review
    assert "不得读取仓库其他文件" in review
    assert "git ls-files --cached --others --exclude-standard" in audit
    assert ".local/spec-work/" in skill and ".local/spec-work/" in audit and ".local/spec-work/" in rules
    assert ".spec-work/" not in skill + audit + rules
    assert "只读取用户指定的文档" in add


def test_plugin_uses_default_skill_paths_without_legacy_installer() -> None:
    assert not (PLUGIN_ROOT / "scripts" / "install.py").exists()
    assert not (PLUGIN_ROOT / "scripts").exists()

    package = json.loads((PLUGIN_ROOT / "package.json").read_text(encoding="utf-8"))
    assert package["name"] == "pi-my-spec"
    assert package["pi"]["extensions"] == ["./extensions/pi-my-spec.ts"]
    assert package["pi"]["skills"] == ["./skills"]


def test_spec_add_deterministic_post_analysis_flow_previews_diffs_and_applies(
    tmp_path: Path,
) -> None:
    cli = SPEC_OPS
    specs = tmp_path / "add" / "specs"
    delta = tmp_path / "add" / "delta"
    preview = tmp_path / "add" / "preview"
    write(specs / "accounts" / "spec.md", main_spec("Accounts", requirement("登录", "允许用户登录")))
    write(
        delta / "accounts" / "spec.md",
        """## ADDED Requirements

### Requirement: 注销

系统 MUST 允许用户注销。

#### Scenario: 主动注销

- **WHEN** 用户选择注销
- **THEN** 系统结束会话
""",
    )

    run_confirmed_workflow(cli, specs, delta, preview, "+### Requirement: 注销")
    assert "### Requirement: 注销" in (specs / "accounts" / "spec.md").read_text(encoding="utf-8")


def test_spec_review_deterministic_duplicate_flow_previews_diffs_and_applies(
    tmp_path: Path,
) -> None:
    cli = SPEC_OPS
    specs = tmp_path / "review" / "specs"
    delta = tmp_path / "review" / "delta"
    preview = tmp_path / "review" / "preview"
    duplicate = requirement("登录", "允许用户登录")
    write(specs / "accounts" / "spec.md", main_spec("Accounts", duplicate, duplicate))
    delta.mkdir(parents=True)

    run_confirmed_workflow(cli, specs, delta, preview, "-### Requirement: 登录")
    assert (specs / "accounts" / "spec.md").read_text(encoding="utf-8").count(
        "### Requirement: 登录"
    ) == 1


def test_spec_audit_deterministic_post_analysis_flow_previews_diffs_and_applies(
    tmp_path: Path,
) -> None:
    cli = SPEC_OPS
    specs = tmp_path / "audit" / "missing-specs"
    delta = tmp_path / "audit" / "delta"
    preview = tmp_path / "audit" / "preview"
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
- **THEN** 系统发送通知
""",
    )

    run_confirmed_workflow(cli, specs, delta, preview, "+### Requirement: 接收通知")
    assert (specs / "notifications" / "spec.md").is_file()


def test_pi_extension_registers_four_default_commands_and_routes_to_skills() -> None:
    source = (PLUGIN_ROOT / "extensions" / "pi-my-spec.ts").read_text(encoding="utf-8")
    for name in SKILL_NAMES:
        assert f'"{name}": "{name}"' in source
    assert "pi.registerCommand(command" in source
    assert "pi.sendUserMessage" in source


def test_my_spec_plugin_is_discoverable_by_pi_claude_and_codex() -> None:
    package_version = json.loads((PLUGIN_ROOT / "package.json").read_text(encoding="utf-8"))["version"]
    for host in (".claude-plugin", ".codex-plugin"):
        manifest = json.loads((PLUGIN_ROOT / host / "plugin.json").read_text(encoding="utf-8"))
        assert manifest["name"] == "my-spec"
        assert manifest["version"] == package_version
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

    before = (specs / "accounts" / "spec.md").read_bytes()
    repeated_validation = run_python(SPEC_OPS, "validate-delta", delta, specs)
    assert repeated_validation.returncode == 0, repeated_validation.stderr
    repeated = run_python(SPEC_OPS, "apply-delta", specs, delta, specs)
    assert repeated.returncode == 0, repeated.stderr
    assert (specs / "accounts" / "spec.md").read_bytes() == before
