---
change: add-pr-flow-plugin
design-doc: docs/superpowers/specs/2026-06-22-pr-flow-plugin-design.md
base-ref: 23fba70e52e53a93c103a4d91fbe671eaa105890
---

# PR Flow Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建适合个人仓库的 `pr-flow` Plugin（插件），覆盖 PR Flow（拉取请求流程）的 diagnose、init、complete、cleanup、hotfix 和 tweak 路径。

**Architecture:** 新增独立 `plugins/pr-flow/` 包，采用多入口 Skill（技能）+ 单个共享 Python（Python 语言）脚本内核。各 Skill 只说明入口和边界，所有确定性流程放在 `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`，测试通过临时 Git（版本管理）仓库、fake `gh` CLI（GitHub 命令行工具）和 fake 命令输出覆盖主流程。

**Tech Stack:** Python 标准库、PyYAML（YAML 解析库）、pytest（Python 测试框架）、Git CLI（版本管理命令行工具）、gh CLI（GitHub 命令行工具）、Codex/Claude plugin manifest（插件清单）。

---

## 文件结构

- Create `plugins/pr-flow/.codex-plugin/plugin.json`: Codex（编码助手）插件清单。
- Create `plugins/pr-flow/.claude-plugin/plugin.json`: Claude（编码助手）插件清单。
- Create `plugins/pr-flow/skills/pr-flow/SKILL.md`: 总入口和 diagnose（诊断）说明。
- Create `plugins/pr-flow/skills/pr-flow-init/SKILL.md`: init（初始化）入口说明。
- Create `plugins/pr-flow/skills/pr-flow-complete/SKILL.md`: complete（完整流程）入口说明。
- Create `plugins/pr-flow/skills/pr-flow-cleanup/SKILL.md`: cleanup（清理）入口说明。
- Create `plugins/pr-flow/skills/pr-flow-hotfix/SKILL.md`: hotfix（热修复）入口说明。
- Create `plugins/pr-flow/skills/pr-flow-tweak/SKILL.md`: tweak（小改动）入口说明。
- Create `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`: 共享命令行脚本和流程内核。
- Create `tests/test_pr_flow_plugin_package.py`: 插件包、Skill、marketplace（插件市场）和 release projection（发布投影）检查。
- Create `tests/test_pr_flow_cli.py`: init、diagnose、complete、cleanup、hotfix、tweak 的脚本行为测试。
- Modify `.claude-plugin/marketplace.json`: 增加 `pr-flow` 本地插件条目。
- Modify `.agents/plugins/marketplace.json`: 增加 `pr-flow` Codex dev marketplace（开发插件市场）条目，使 `scripts/check.py build` 保持通过。
- Modify `.release-flow/projection.yaml`: 在 `codex-marketplace` generator（生成器）中增加 `pr-flow`。
- Modify `openspec/changes/add-pr-flow-plugin/tasks.md`: 每个实现阶段验证通过后再勾选任务。

## Task 1: Plugin Package Skeleton

**Files:**
- Create: `tests/test_pr_flow_plugin_package.py`
- Create: `plugins/pr-flow/.codex-plugin/plugin.json`
- Create: `plugins/pr-flow/.claude-plugin/plugin.json`
- Create: `plugins/pr-flow/skills/pr-flow/SKILL.md`
- Create: `plugins/pr-flow/skills/pr-flow-init/SKILL.md`
- Create: `plugins/pr-flow/skills/pr-flow-complete/SKILL.md`
- Create: `plugins/pr-flow/skills/pr-flow-cleanup/SKILL.md`
- Create: `plugins/pr-flow/skills/pr-flow-hotfix/SKILL.md`
- Create: `plugins/pr-flow/skills/pr-flow-tweak/SKILL.md`
- Create: `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`
- Modify: `.claude-plugin/marketplace.json`
- Modify: `.agents/plugins/marketplace.json`
- Modify: `.release-flow/projection.yaml`

- [x] **Step 1: Write failing package tests**

Create `tests/test_pr_flow_plugin_package.py`:

```python
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "pr-flow"
SCRIPT = PLUGIN_ROOT / "skills" / "pr-flow" / "scripts" / "pr_flow.py"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_pr_flow_manifests_are_valid() -> None:
    codex_manifest = read_json(PLUGIN_ROOT / ".codex-plugin" / "plugin.json")
    claude_manifest = read_json(PLUGIN_ROOT / ".claude-plugin" / "plugin.json")

    assert codex_manifest["name"] == "pr-flow"
    assert claude_manifest["name"] == "pr-flow"
    assert codex_manifest["version"] == claude_manifest["version"]
    assert codex_manifest["skills"] == "./skills"
    assert claude_manifest["skills"] == "./skills"
    assert codex_manifest["description"]
    assert claude_manifest["description"]


def test_pr_flow_skill_entrypoints_and_script_are_packaged() -> None:
    skill_names = [
        "pr-flow",
        "pr-flow-init",
        "pr-flow-complete",
        "pr-flow-cleanup",
        "pr-flow-hotfix",
        "pr-flow-tweak",
    ]
    for skill_name in skill_names:
        skill = PLUGIN_ROOT / "skills" / skill_name / "SKILL.md"
        assert skill.is_file(), skill
        text = skill.read_text(encoding="utf-8")
        assert "pr_flow.py" in text
        assert "PR Flow" in text

    assert SCRIPT.is_file()


def test_pr_flow_cli_parser_accepts_documented_commands() -> None:
    for command in ["diagnose", "init", "complete", "cleanup", "hotfix", "tweak"]:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), command, "--help"],
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0
        assert command in result.stdout


def test_claude_repo_marketplace_includes_pr_flow() -> None:
    catalog = read_json(REPO_ROOT / ".claude-plugin" / "marketplace.json")
    entries = [plugin for plugin in catalog["plugins"] if plugin.get("name") == "pr-flow"]

    assert entries == [
        {
            "name": "pr-flow",
            "source": "./plugins/pr-flow",
            "description": "PR Flow plugin for Codex and Claude agents",
        }
    ]


def test_codex_dev_marketplace_includes_pr_flow() -> None:
    catalog = read_json(REPO_ROOT / ".agents" / "plugins" / "marketplace.json")
    entries = [plugin for plugin in catalog["plugins"] if plugin.get("name") == "pr-flow"]

    assert entries == [
        {
            "name": "pr-flow",
            "source": {"source": "local", "path": "./plugins/pr-flow"},
            "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
            "category": "Developer Tools",
        }
    ]


def test_release_projection_includes_pr_flow() -> None:
    text = (REPO_ROOT / ".release-flow" / "projection.yaml").read_text(encoding="utf-8")

    assert "      - pr-flow" in text
```

- [x] **Step 2: Run package tests and verify they fail**

Run:

```powershell
python -m pytest tests/test_pr_flow_plugin_package.py -q
```

Expected: FAIL because `plugins/pr-flow/` and marketplace entries do not exist yet.

- [x] **Step 3: Add plugin manifests**

Create both manifests with the same version used by current plugins:

```json
{
  "name": "pr-flow",
  "version": "0.1.7",
  "description": "PR Flow Plugin（拉取请求流程插件）",
  "skills": "./skills"
}
```

- [x] **Step 4: Add Skill entrypoints**

Each `SKILL.md` must include front matter, a short boundary section, and a command example that calls the shared script. Use this pattern and adjust the command name per Skill:

```markdown
---
name: pr-flow-cleanup
description: "清理已合并 PR。Use when 需要执行 PR Flow cleanup，删除已合并 PR 的 head branch 并同步 base branch。"
---

# PR Flow Cleanup

本 Skill 只调用共享 `pr_flow.py` 脚本，不复制流程逻辑。

## 命令

```powershell
python ../pr-flow/scripts/pr_flow.py cleanup --project .
```
```

Required command words:
- `pr-flow`: `diagnose`
- `pr-flow-init`: `init`
- `pr-flow-complete`: `complete`
- `pr-flow-cleanup`: `cleanup`
- `pr-flow-hotfix`: `hotfix`
- `pr-flow-tweak`: `tweak`

- [x] **Step 5: Add initial CLI parser**

Create `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py` with command parser behavior:

```python
from __future__ import annotations

import argparse
from collections.abc import Sequence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pr_flow.py")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ["diagnose", "init", "complete", "cleanup", "hotfix", "tweak"]:
        subparsers.add_parser(command)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    build_parser().parse_args(argv)
    print("status: not_implemented")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
```

- [x] **Step 6: Register plugin in marketplace and release projection**

Append `pr-flow` to:
- `.claude-plugin/marketplace.json`
- `.agents/plugins/marketplace.json`
- `.release-flow/projection.yaml`

Keep the existing order stable by adding `pr-flow` after `cross-agent-review`.

- [x] **Step 7: Run package tests**

Run:

```powershell
python -m pytest tests/test_pr_flow_plugin_package.py -q
```

Expected: PASS.

- [x] **Step 8: Commit package skeleton**

```bash
git add plugins/pr-flow tests/test_pr_flow_plugin_package.py .claude-plugin/marketplace.json .agents/plugins/marketplace.json .release-flow/projection.yaml
git commit -m "feat: 新增 pr-flow 插件骨架"
```

## Task 2: Init Configuration

**Files:**
- Create: `tests/test_pr_flow_cli.py`
- Modify: `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`

- [x] **Step 1: Write failing init tests**

Create `tests/test_pr_flow_cli.py`:

```python
import json
import subprocess
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    REPO_ROOT
    / "plugins"
    / "pr-flow"
    / "skills"
    / "pr-flow"
    / "scripts"
    / "pr_flow.py"
)


def run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd or REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )


def test_init_creates_config_template_and_gitignore(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()

    result = run("init", "--project", str(project), "--base-branch", "main")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: initialized" in result.stdout
    assert "GitHub Rulesets suggestion" in result.stdout

    config = yaml.safe_load((project / ".pr-flow" / "config.yaml").read_text(encoding="utf-8"))
    assert config["defaults"]["baseBranch"] == "main"
    assert config["defaults"]["mergeStrategy"] == "merge"
    assert config["defaults"]["reviewGate"]["mode"] == "github"
    assert config["defaults"]["wait"] == {"timeoutSeconds": 600, "pollSeconds": 15}
    assert config["defaults"]["pr"]["bodyTemplatePath"] == ".pr-flow/pr-template.md"
    assert config["branches"]["main"]["remote"] == "origin"
    assert config["branches"]["main"]["allowHotfixPush"] is False

    template = (project / ".pr-flow" / "pr-template.md").read_text(encoding="utf-8")
    for section in ["Summary", "Scope", "Verification", "Risk", "Rollback"]:
        assert f"## {section}" in template

    assert (project / ".pr-flow" / ".gitignore").read_text(encoding="utf-8") == "/runs/\n/last-status.json\n"


def test_init_does_not_call_gh_api(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()

    result = run("init", "--project", str(project))

    assert result.returncode == 0
    assert "gh api" not in result.stdout
    assert "Rulesets written" not in result.stdout
```

- [x] **Step 2: Run init tests and verify they fail**

Run:

```powershell
python -m pytest tests/test_pr_flow_cli.py::test_init_creates_config_template_and_gitignore tests/test_pr_flow_cli.py::test_init_does_not_call_gh_api -q
```

Expected: FAIL because init is not implemented.

- [x] **Step 3: Implement init with small helpers**

Add helpers in `pr_flow.py`:
- `resolve_project(path: Path) -> Path`
- `write_text_if_missing(path: Path, text: str) -> None`
- `default_config(base_branch: str) -> dict`
- `run_init(args: argparse.Namespace) -> int`

Implementation constraints:
- Write only `.pr-flow/config.yaml`, `.pr-flow/pr-template.md`, `.pr-flow/.gitignore`.
- Do not run `gh`.
- Do not add dry-run behavior.
- Print `status: initialized`.

- [x] **Step 4: Run init tests**

Run:

```powershell
python -m pytest tests/test_pr_flow_cli.py::test_init_creates_config_template_and_gitignore tests/test_pr_flow_cli.py::test_init_does_not_call_gh_api -q
```

Expected: PASS.

- [x] **Step 5: Commit init**

```bash
git add plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py tests/test_pr_flow_cli.py
git commit -m "feat: 实现 pr-flow 初始化配置"
```

## Task 3: Config Loading, Command Runner, And Status Files

**Files:**
- Modify: `tests/test_pr_flow_cli.py`
- Modify: `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`

- [x] **Step 1: Add failing tests for config validation and status persistence**

Append:

```python
def test_missing_config_reports_exception_required(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()

    result = run("diagnose", "--project", str(project))

    assert result.returncode == 1
    assert "status: EXCEPTION_REQUIRED" in result.stdout
    assert "missing_config" in result.stdout


def test_status_file_is_written_for_stop_state(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()

    run("init", "--project", str(project))
    result = run("diagnose", "--project", str(project))

    assert result.returncode == 1
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] in {"PUSH_REQUIRED", "EXCEPTION_REQUIRED"}
    assert status["command"] == "diagnose"
```

- [x] **Step 2: Run tests and verify they fail**

Run:

```powershell
python -m pytest tests/test_pr_flow_cli.py::test_missing_config_reports_exception_required tests/test_pr_flow_cli.py::test_status_file_is_written_for_stop_state -q
```

Expected: FAIL because status writing and config loading do not exist.

- [x] **Step 3: Implement config and status helpers**

Add helpers:
- `load_config(project: Path) -> dict`
- `write_status(project: Path, command: str, status: str, details: dict) -> None`
- `print_stop(status: str, message: str) -> None`
- `git(project: Path, *args: str) -> subprocess.CompletedProcess[str]`
- `gh(project: Path, *args: str) -> subprocess.CompletedProcess[str]`

All command helpers must return captured stdout/stderr and avoid shell string composition.

- [x] **Step 4: Run focused tests**

Run:

```powershell
python -m pytest tests/test_pr_flow_cli.py::test_missing_config_reports_exception_required tests/test_pr_flow_cli.py::test_status_file_is_written_for_stop_state -q
```

Expected: PASS.

- [x] **Step 5: Commit config/status foundation**

```bash
git add plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py tests/test_pr_flow_cli.py
git commit -m "feat: 添加 pr-flow 配置读取和状态记录"
```

## Task 4: Diagnose Stop States

**Files:**
- Modify: `tests/test_pr_flow_cli.py`
- Modify: `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`

- [x] **Step 1: Add Git fixture helpers**

Append these helpers to `tests/test_pr_flow_cli.py`:

```python
def git(project: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(project), *args],
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


def init_repo(project: Path) -> str:
    project.mkdir(parents=True)
    git(project, "init", "-b", "main")
    git(project, "config", "user.email", "test@example.invalid")
    git(project, "config", "user.name", "Test User")
    (project / "README.md").write_text("baseline\n", encoding="utf-8")
    git(project, "add", "README.md")
    git(project, "commit", "-m", "baseline")
    return git(project, "rev-parse", "HEAD")
```

- [x] **Step 2: Add failing diagnose tests**

Append:

```python
def test_diagnose_outputs_push_required_without_upstream(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    init_repo(project)
    run("init", "--project", str(project))
    git(project, "checkout", "-b", "feature/demo")

    result = run("diagnose", "--project", str(project), cwd=project)

    assert result.returncode == 1
    assert "status: PUSH_REQUIRED" in result.stdout
    assert "push" in result.stdout


def test_diagnose_outputs_exception_for_unknown_gh_failure(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    init_repo(project)
    run("init", "--project", str(project))

    result = run("diagnose", "--project", str(project), cwd=project)

    assert result.returncode == 1
    assert "status: EXCEPTION_REQUIRED" in result.stdout
```

- [x] **Step 3: Run diagnose tests and verify they fail**

Run:

```powershell
python -m pytest tests/test_pr_flow_cli.py::test_diagnose_outputs_push_required_without_upstream tests/test_pr_flow_cli.py::test_diagnose_outputs_exception_for_unknown_gh_failure -q
```

Expected: FAIL because diagnose logic is incomplete.

- [x] **Step 4: Implement diagnose state discovery**

Implement:
- current branch discovery with `git branch --show-current`
- upstream discovery with `git rev-parse --abbrev-ref --symbolic-full-name @{u}`
- dirty worktree discovery with `git status --short`
- PR lookup through `gh pr view --json number,state,mergeStateStatus,reviewDecision,headRefName,baseRefName,statusCheckRollup`

Stop state mapping:
- no upstream -> `PUSH_REQUIRED`
- incomplete checks -> `DISPATCH_REQUIRED`
- failing checks or blocking review -> `REPLY_OR_FIX_REQUIRED`
- unknown command or parse failure -> `EXCEPTION_REQUIRED`

- [x] **Step 5: Add fake `gh` tests for `DISPATCH_REQUIRED` and `REPLY_OR_FIX_REQUIRED`**

Use a temporary `gh.cmd`/`gh.bat` in `PATH` that prints fixed JSON:

```python
def fake_gh_bin(tmp_path: Path, stdout: str, exit_code: int = 0) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    script = f"@echo off\r\necho {stdout}\r\nexit /b {exit_code}\r\n"
    (bin_dir / "gh.cmd").write_text(script, encoding="utf-8")
    (bin_dir / "gh.bat").write_text(script, encoding="utf-8")
    return bin_dir
```

Add tests where fake JSON has pending checks and failing checks.

- [x] **Step 6: Run diagnose tests**

Run:

```powershell
python -m pytest tests/test_pr_flow_cli.py -q
```

Expected: current init/config/diagnose tests pass.

- [x] **Step 7: Commit diagnose**

```bash
git add plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py tests/test_pr_flow_cli.py
git commit -m "feat: 实现 pr-flow 诊断状态"
```

## Task 5: PR Sync, Checks, And Review Gate

**Files:**
- Modify: `tests/test_pr_flow_cli.py`
- Modify: `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`

- [x] **Step 1: Write failing tests for PR creation and sync commands**

Add tests with fake `gh` command logs:

```python
def test_complete_creates_pr_when_no_pr_exists(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    init_repo(project)
    run("init", "--project", str(project))
    git(project, "checkout", "-b", "feature/demo")

    gh_log = tmp_path / "gh.log"
    bin_dir = fake_gh_sequence(
        tmp_path,
        gh_log,
        [
            (1, ""),
            (0, '{"number":12,"headRefOid":"' + git(project, "rev-parse", "HEAD") + '"}'),
            (0, '{"statusCheckRollup":[],"reviewDecision":"APPROVED"}'),
            (0, ""),
            (0, '{"merged":true,"headRefName":"feature/demo","baseRefName":"main"}'),
        ],
    )

    result = run_with_path("complete", "--project", str(project), cwd=project, path_prefix=bin_dir)

    assert "pr create" in gh_log.read_text(encoding="utf-8")
    assert "status:" in result.stdout
```

Define `fake_gh_sequence` and `run_with_path` in the test file. The fake `gh` should log arguments and return outputs in order.

- [x] **Step 2: Write failing review gate tests**

Add focused tests for modes:
- `reviewGate.mode: skip` does not call review status.
- `reviewGate.mode: github` rejects `CHANGES_REQUESTED`.
- `reviewGate.mode: local` reads configured `review-pass.json`.
- `reviewGate.mode: dual` requires both GitHub and local evidence.

Local evidence fixture:

```python
def write_review_pass(path: Path, base_ref: str, head_ref: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "status": "pass",
                "base_ref": base_ref,
                "head_ref": head_ref,
                "diff_fingerprint": "test-diff",
                "blocking_findings": 0,
                "report_hash": "sha256:test",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
```

- [x] **Step 3: Run tests and verify they fail**

Run:

```powershell
python -m pytest tests/test_pr_flow_cli.py -q
```

Expected: FAIL in PR sync and review gate tests.

- [x] **Step 4: Implement PR sync and check parsing helpers**

Implement:
- `find_pr(project) -> dict | None`
- `create_pr(project, config) -> dict`
- `sync_pr(project, pr) -> dict`
- `wait_for_checks(project, pr, wait_config) -> StopState | None`
- `check_review_gate(project, config, pr) -> StopState | None`
- `load_local_review_evidence(project, config) -> dict`

Keep wait tests fast by allowing `wait.timeoutSeconds: 0` in test config.

- [x] **Step 5: Run focused tests**

Run:

```powershell
python -m pytest tests/test_pr_flow_cli.py -q
```

Expected: tests for init, diagnose, PR sync, checks, and review gate pass.

- [x] **Step 6: Commit PR sync and review gate**

```bash
git add plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py tests/test_pr_flow_cli.py
git commit -m "feat: 添加 PR 同步和审查门禁"
```

## Task 6: Cleanup For Merged PR (#51)

**Files:**
- Modify: `tests/test_pr_flow_cli.py`
- Modify: `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`

- [x] **Step 1: Write failing cleanup success test**

Use a bare remote to test real branch deletion:

```python
def test_cleanup_merged_pr_deletes_remote_and_local_head_then_syncs_base(tmp_path: Path) -> None:
    remote = tmp_path / "remote.git"
    project = tmp_path / "repo"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, text=True, capture_output=True)
    init_repo(project)
    git(project, "remote", "add", "origin", str(remote))
    git(project, "push", "-u", "origin", "main")
    git(project, "checkout", "-b", "feature/demo")
    (project / "feature.txt").write_text("demo\n", encoding="utf-8")
    git(project, "add", "feature.txt")
    git(project, "commit", "-m", "feature")
    git(project, "push", "-u", "origin", "feature/demo")
    git(project, "checkout", "main")
    git(project, "merge", "--no-ff", "feature/demo", "-m", "merge feature")
    git(project, "push", "origin", "main")
    git(project, "checkout", "feature/demo")
    run("init", "--project", str(project))

    bin_dir = fake_gh_json(
        tmp_path,
        {
            "number": 12,
            "state": "MERGED",
            "headRefName": "feature/demo",
            "baseRefName": "main",
            "headRepositoryOwner": {"login": "owner"},
        },
    )

    result = run_with_path("cleanup", "--project", str(project), "--pr", "12", cwd=project, path_prefix=bin_dir)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: cleanup_complete" in result.stdout
    assert git(project, "branch", "--show-current") == "main"
    assert "feature/demo" not in git(project, "branch")
    assert subprocess.run(["git", "-C", str(remote), "show-ref", "--verify", "refs/heads/feature/demo"], text=True, capture_output=True).returncode == 1
```

- [x] **Step 2: Write failing cleanup refusal tests**

Cover:
- PR state is not `MERGED`.
- worktree has `git status --short` output.
- head branch equals protected base branch.
- local current branch does not match PR head branch when cleanup starts.

Expected output includes `EXCEPTION_REQUIRED`.

- [x] **Step 3: Run cleanup tests and verify they fail**

Run:

```powershell
python -m pytest tests/test_pr_flow_cli.py::test_cleanup_merged_pr_deletes_remote_and_local_head_then_syncs_base -q
```

Expected: FAIL because cleanup is not implemented.

- [x] **Step 4: Implement cleanup**

Implement sequence:
- Load PR through `gh pr view`.
- Require state `MERGED`.
- Require clean worktree.
- Require current branch equals PR head branch, unless command has an explicit safe override already covered by tests.
- Refuse if head branch equals base branch.
- Delete remote with `git push <remote> --delete <headRefName>`.
- Checkout base with `git checkout <baseRefName>`.
- Fetch and fast-forward with `git pull --ff-only <remote> <baseRefName>`.
- Delete local head with `git branch -d <headRefName>`.
- Print final branch state.

- [x] **Step 5: Run cleanup tests**

Run:

```powershell
python -m pytest tests/test_pr_flow_cli.py -q
```

Expected: cleanup success and refusal cases pass.

- [x] **Step 6: Commit cleanup**

```bash
git add plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py tests/test_pr_flow_cli.py
git commit -m "feat: 实现已合并 PR 清理"
```

## Task 7: Head-Locked Merge And Complete Orchestration

**Files:**
- Modify: `tests/test_pr_flow_cli.py`
- Modify: `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`

- [x] **Step 1: Write failing merge strategy tests**

Add fake `gh` log tests for:
- `mergeStrategy: merge` calls `gh pr merge --merge --match-head-commit <sha>`.
- `mergeStrategy: squash` calls `--squash`.
- `mergeStrategy: rebase` calls `--rebase`.
- Moved head rejects before merge and outputs `EXCEPTION_REQUIRED`.

- [x] **Step 2: Write complete happy path orchestration test**

Use fake `gh` outputs to assert ordering:

```python
def test_complete_runs_sync_checks_review_merge_and_cleanup_in_order(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    init_repo(project)
    run("init", "--project", str(project))
    git(project, "checkout", "-b", "feature/demo")
    head = git(project, "rev-parse", "HEAD")

    gh_log = tmp_path / "gh.log"
    bin_dir = fake_gh_sequence_for_complete(tmp_path, gh_log, head)

    result = run_with_path("complete", "--project", str(project), cwd=project, path_prefix=bin_dir)

    assert result.returncode in {0, 1}
    log = gh_log.read_text(encoding="utf-8")
    assert "pr view" in log
    assert "pr merge" in log
    assert "--match-head-commit " + head in log
```

- [x] **Step 3: Run tests and verify they fail**

Run:

```powershell
python -m pytest tests/test_pr_flow_cli.py -q
```

Expected: FAIL in merge and complete orchestration tests.

- [x] **Step 4: Implement merge and complete orchestration**

Implement:
- `merge_pr(project, config, pr) -> None`
- `run_complete(args) -> int`
- head OID lookup immediately before merge
- merge command with configured strategy and `--match-head-commit`
- call cleanup after successful merge

Do not require authorization phrase for `merge` or `complete`.

- [x] **Step 5: Run lifecycle tests**

Run:

```powershell
python -m pytest tests/test_pr_flow_cli.py -q
```

Expected: all current CLI tests pass.

- [x] **Step 6: Commit complete lifecycle**

```bash
git add plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py tests/test_pr_flow_cli.py
git commit -m "feat: 实现 PR 完整流程"
```

## Task 8: Authorization Phrase And Hotfix

**Files:**
- Modify: `tests/test_pr_flow_cli.py`
- Modify: `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`

- [x] **Step 1: Write failing authorization phrase tests**

Append:

```python
def md5_text(value: str) -> str:
    import hashlib

    return hashlib.md5(value.encode("utf-8")).hexdigest()


def test_authorization_phrase_matches_md5_hash(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    init_repo(project)
    run("init", "--project", str(project))
    config_path = project / ".pr-flow" / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["authorization"] = {"phraseHashAlgorithm": "md5", "phraseHash": md5_text("我确认")}
    config_path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")

    result = run("hotfix", "--project", str(project), "--target", "main", "--authorization-phrase", "wrong")

    assert result.returncode == 1
    assert "authorization_phrase_mismatch" in result.stdout
```

- [x] **Step 2: Write failing hotfix tests**

Cover:
- target branch missing `allowHotfixPush: true` -> refuse.
- current commit not based on remote target head -> refuse.
- `hotfix.verifyCommand` fails -> refuse.
- valid hotfix pushes `HEAD:refs/heads/main` and reads back remote.
- audit record contains target branch, before/after commit, actor, timestamp, verification result.

- [x] **Step 3: Run hotfix tests and verify they fail**

Run:

```powershell
python -m pytest tests/test_pr_flow_cli.py -q
```

Expected: FAIL in authorization and hotfix tests.

- [x] **Step 4: Implement authorization phrase helpers**

Implement:
- `verify_authorization_phrase(config: dict, phrase: str) -> None`
- support only `phraseHashAlgorithm: md5`
- never print or persist the phrase
- current command only; no state file for authorization

- [x] **Step 5: Implement hotfix**

Implement:
- Require `--target`.
- Resolve branch config from `defaults` + `branches[target]`.
- Require `allowHotfixPush: true`.
- Fetch remote target.
- Require `git merge-base HEAD origin/<target>` equals `origin/<target>`.
- Run configured `hotfix.verifyCommand` with `subprocess.run(..., shell=False)` when split safely, or document that complex commands must be run through the platform shell and test exact behavior.
- Require authorization phrase after verification succeeds.
- Push `HEAD:refs/heads/<target>`.
- Fetch/read back remote target and compare to `HEAD`.
- Write minimal audit JSON under `.pr-flow/runs/`.

- [x] **Step 6: Run hotfix tests**

Run:

```powershell
python -m pytest tests/test_pr_flow_cli.py -q
```

Expected: hotfix tests pass.

- [x] **Step 7: Commit hotfix**

```bash
git add plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py tests/test_pr_flow_cli.py
git commit -m "feat: 添加 hotfix 直推路径"
```

## Task 9: Tweak Path

**Files:**
- Modify: `tests/test_pr_flow_cli.py`
- Modify: `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`

- [ ] **Step 1: Write failing tweak tests**

Append tests for:
- missing `--reason` returns error.
- tweak creates or syncs PR.
- tweak skips review gate.
- tweak still waits checks, merges, and calls cleanup.
- PR body includes tweak marker and reason.

Example assertion:

```python
def test_tweak_requires_reason(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    init_repo(project)
    run("init", "--project", str(project))

    result = run("tweak", "--project", str(project), cwd=project)

    assert result.returncode == 2
    assert "tweak_requires_reason" in result.stdout
```

- [ ] **Step 2: Run tweak tests and verify they fail**

Run:

```powershell
python -m pytest tests/test_pr_flow_cli.py -q
```

Expected: FAIL in tweak tests.

- [ ] **Step 3: Implement tweak orchestration**

Implement `run_tweak(args)`:
- Require `--reason`.
- Reuse PR sync/checks/merge/cleanup helpers from complete.
- Override review gate to `skip`.
- Insert marker into PR body:

```markdown
## Tweak Path

Review gate skipped for non-bug small change.

Reason: <reason>
```

Do not restrict file paths.

- [ ] **Step 4: Run tweak tests**

Run:

```powershell
python -m pytest tests/test_pr_flow_cli.py -q
```

Expected: tweak tests pass.

- [ ] **Step 5: Commit tweak**

```bash
git add plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py tests/test_pr_flow_cli.py
git commit -m "feat: 添加 tweak PR 路径"
```

## Task 10: Package Validation And Release Projection

**Files:**
- Modify: `tests/test_pr_flow_plugin_package.py`
- Modify: `tests/test_local_plugin_build_checks.py` only if existing build checks need explicit `pr-flow` assertions
- Modify: `.release-flow/projection.yaml`
- Modify: `.claude-plugin/marketplace.json`
- Modify: `.agents/plugins/marketplace.json`

- [ ] **Step 1: Add current-repo validation test**

Add to `tests/test_pr_flow_plugin_package.py`:

```python
def test_repo_build_checks_include_pr_flow() -> None:
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "check.py"), "build"],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: build checks passed" in result.stdout
```

- [ ] **Step 2: Run build validation and fix registration drift**

Run:

```powershell
python scripts/check.py build
```

Expected: exit code 0 and `status: build checks passed`.

If this fails with projection or marketplace mismatch, update only the three registration files listed in this task.

- [ ] **Step 3: Run package tests**

Run:

```powershell
python -m pytest tests/test_pr_flow_plugin_package.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit packaging validation**

```bash
git add tests/test_pr_flow_plugin_package.py tests/test_local_plugin_build_checks.py .release-flow/projection.yaml .claude-plugin/marketplace.json .agents/plugins/marketplace.json
git commit -m "test: 覆盖 pr-flow 插件包校验"
```

## Task 11: End-To-End Regression And OpenSpec Closure

**Files:**
- Modify: `openspec/changes/add-pr-flow-plugin/tasks.md`

- [ ] **Step 1: Run focused test suite**

Run:

```powershell
python -m pytest tests/test_pr_flow_plugin_package.py tests/test_pr_flow_cli.py -q
```

Expected: PASS.

- [ ] **Step 2: Run plugin build checks**

Run:

```powershell
python scripts/check.py build
```

Expected: exit code 0 and `status: build checks passed`.

- [ ] **Step 3: Run full repository verification**

Run:

```powershell
python scripts/check.py verify
```

Expected: exit code 0 and full pytest suite passes.

- [ ] **Step 4: Run OpenSpec validation**

Run:

```powershell
openspec validate add-pr-flow-plugin --type change --strict
```

Expected: change is valid.

- [ ] **Step 5: Mark OpenSpec tasks complete**

Update `openspec/changes/add-pr-flow-plugin/tasks.md` only after the matching tests and validations pass. Do not check off tasks before evidence exists.

- [ ] **Step 6: Write verification report**

Create a report under `docs/superpowers/reports/` only if the project workflow requires it at implementation time. The report must list:
- focused pytest command and result,
- `python scripts/check.py build` result,
- `python scripts/check.py verify` result,
- OpenSpec validation result,
- any intentionally skipped non-goals.

- [ ] **Step 7: Commit closure**

```bash
git add openspec/changes/add-pr-flow-plugin/tasks.md docs/superpowers/reports
git commit -m "chore: 完成 pr-flow 验证记录"
```

## Self-Review

Spec coverage:
- Plugin package and Skill entrypoints are covered by Task 1 and Task 10.
- `.pr-flow/config.yaml`, PR template, `.gitignore`, and Rulesets suggestion are covered by Task 2.
- Fixed stop states `PUSH_REQUIRED`, `DISPATCH_REQUIRED`, `REPLY_OR_FIX_REQUIRED`, and `EXCEPTION_REQUIRED` are covered by Tasks 3 and 4.
- Complete lifecycle, checks, review gate, head-locked merge, and merge strategy are covered by Tasks 5 and 7.
- Cleanup #51 success and refusal paths are covered by Task 6.
- Hotfix allow-list, base match, verify command, authorization phrase, remote readback, and audit record are covered by Task 8.
- Tweak reason, PR body marker, review gate skip, checks, merge, and cleanup are covered by Task 9.
- Release projection and package validation are covered by Task 10.
- Full verification and OpenSpec task closure are covered by Task 11.

Forbidden wording scan:
- No task uses forbidden unfinished-work wording from the planning skill.
- Each task names exact files, commands, expected outcomes, and success criteria.

Type consistency:
- Planned helper names are consistent across tests and implementation steps: `run_init`, `run_diagnose`, `run_complete`, `run_cleanup`, `run_hotfix`, `run_tweak`, `load_config`, `write_status`, `verify_authorization_phrase`.
- Stop state tokens stay exact: `PUSH_REQUIRED`, `DISPATCH_REQUIRED`, `REPLY_OR_FIX_REQUIRED`, `EXCEPTION_REQUIRED`.
