---
change: agent-guard-marketplace-subscription
design-doc: docs/superpowers/specs/2026-06-17-agent-guard-marketplace-subscription-design.md
base-ref: b368f7a0852424acb7a17720895459dfe7930fac
---

# Agent Guard Marketplace Subscription Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 Agent Guard 发布路径收敛为 Codex 与 Claude 都可订阅的 marketplace（市场）发布形态。

**Architecture:** `plugins/agent-guard` 保持为唯一自包含插件包。Codex catalog（目录）写入 `.agents/plugins/marketplace.json`，Claude catalog 写入 `.claude-plugin/marketplace.json`，两者都解析到 `plugins/agent-guard`。`install_agent_guard_plugin.py` 只负责包校验、catalog 生成/验证和 dry-run 输出，不初始化 profile、hook 或 git config。

**Tech Stack:** Python 3 stdlib、pytest、PowerShell 脚本删除、OpenSpec delta specs。

---

## File Structure

- Modify: `tests/test_agent_guard_plugin_installer.py`
  Installer contract tests for `--target`, `--scope`, repo/personal catalog paths, branch reference, and legacy entry rejection.
- Modify: `tests/test_agent_guard_plugin_package.py`
  Package tests for Codex/Claude manifests, repo catalogs, self-contained resources, and absence of legacy root skills.
- Create: `tests/test_agent_guard_skill_entrypoints.py`
  Move the non-install Skill entrypoint tests from `tests/test_user_skill_install.py` here.
- Delete: `tests/test_user_skill_install.py`
  Remove tests that execute user-level Skill install and Claude Junction flows.
- Modify: `plugins/agent-guard/skills/agent-guard/scripts/install_agent_guard_plugin.py`
  Refactor installer into package validation, catalog generation/validation, and CLI orchestration.
- Create: `.agents/plugins/marketplace.json`
  Codex repo marketplace catalog.
- Create: `.claude-plugin/marketplace.json`
  Claude repo marketplace catalog.
- Delete: `scripts/install/install_user_skill.ps1`
- Delete: `scripts/install/sync_claude_junction.ps1`
- Delete: `scripts/install/verify_install.py`
- Modify or delete: `scripts/install/README.md`
  Remove old user-level Skill installation instructions.
- Modify: `openspec/changes/agent-guard-marketplace-subscription/tasks.md`
  Check off completed tasks as implementation lands.

## Task 1: Red Contract Tests For Marketplace Installer

**Files:**
- Modify: `tests/test_agent_guard_plugin_installer.py`

- [x] **Step 1: Replace old common installer args with target/scope-aware paths**

Use this helper shape in `tests/test_agent_guard_plugin_installer.py`:

```python
def common_args(tmp_path: Path) -> list[str]:
    repo_root = tmp_path / "repo-marketplace"
    return [
        "--plugin-source",
        str(PLUGIN_ROOT),
        "--codex-repo-marketplace",
        str(repo_root / ".agents" / "plugins" / "marketplace.json"),
        "--claude-repo-marketplace",
        str(repo_root / ".claude-plugin" / "marketplace.json"),
        "--codex-personal-marketplace",
        str(tmp_path / "codex-personal" / ".agents" / "plugins" / "marketplace.json"),
        "--claude-personal-marketplace",
        str(tmp_path / "claude-personal" / ".claude-plugin" / "marketplace.json"),
        "--release-ref",
        "marketplace",
    ]
```

- [x] **Step 2: Add dry-run test for target/scope separation**

Replace `test_dry_run_lists_codex_and_claude_targets_without_writing` with:

```python
def test_dry_run_lists_selected_targets_and_scopes_without_writing(tmp_path: Path) -> None:
    result = run_installer(["dry-run", *common_args(tmp_path), "--target", "all", "--scope", "all"])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: dry_run" in result.stdout
    assert "target: all" in result.stdout
    assert "scope: all" in result.stdout
    assert "release_ref: marketplace" in result.stdout
    assert "codex_repo_marketplace:" in result.stdout
    assert "claude_repo_marketplace:" in result.stdout
    assert "codex_personal_marketplace:" in result.stdout
    assert "claude_personal_marketplace:" in result.stdout
    assert "project_hooks: not_installed" in result.stdout
    assert "git_config: not_modified" in result.stdout
    assert not (tmp_path / "repo-marketplace").exists()
    assert not (tmp_path / "codex-personal").exists()
    assert not (tmp_path / "claude-personal").exists()
```

- [x] **Step 3: Add authorization tests for target and scope**

Replace `test_install_requires_explicit_target_and_authorization` with:

```python
def test_install_requires_target_scope_and_authorization(tmp_path: Path) -> None:
    missing_target = run_installer(["install", *common_args(tmp_path), "--scope", "repo", "--authorize-install"])
    missing_scope = run_installer(["install", *common_args(tmp_path), "--target", "codex", "--authorize-install"])
    missing_authorization = run_installer(["install", *common_args(tmp_path), "--target", "codex", "--scope", "repo"])

    assert missing_target.returncode == 2
    assert "install requires --target" in missing_target.stderr
    assert missing_scope.returncode == 2
    assert "install requires --scope" in missing_scope.stderr
    assert missing_authorization.returncode == 2
    assert "install requires --authorize-install" in missing_authorization.stderr
```

- [x] **Step 4: Add install test for repeatable repo and personal catalog writes**

Replace `test_authorized_install_is_repeatable_and_updates_marketplaces` with:

```python
def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_authorized_install_is_repeatable_and_updates_marketplace_catalogs(tmp_path: Path) -> None:
    args = ["install", *common_args(tmp_path), "--target", "all", "--scope", "all", "--authorize-install"]

    first = run_installer(args)
    second = run_installer(args)

    assert first.returncode == 0, first.stdout + first.stderr
    assert second.returncode == 0, second.stdout + second.stderr
    assert "status: installed" in second.stdout

    codex_repo = read_json(tmp_path / "repo-marketplace" / ".agents" / "plugins" / "marketplace.json")
    claude_repo = read_json(tmp_path / "repo-marketplace" / ".claude-plugin" / "marketplace.json")
    codex_personal = read_json(tmp_path / "codex-personal" / ".agents" / "plugins" / "marketplace.json")
    claude_personal = read_json(tmp_path / "claude-personal" / ".claude-plugin" / "marketplace.json")

    assert codex_repo["plugins"][0]["source"] == {"source": "local", "path": "./plugins/agent-guard"}
    assert codex_repo["plugins"][0]["policy"] == {"installation": "AVAILABLE", "authentication": "ON_INSTALL"}
    assert claude_repo["plugins"][0]["source"] == "./plugins/agent-guard"
    assert codex_personal["plugins"][0]["name"] == "agent-guard"
    assert claude_personal["plugins"][0]["name"] == "agent-guard"
    assert not (tmp_path / "target-project" / ".codex" / "hooks.json").exists()
    assert not (tmp_path / "target-project" / ".githooks").exists()
    assert not (tmp_path / "target-project" / ".git" / "config").exists()
```

- [x] **Step 5: Add verify test for marketplace entries and legacy entry rejection**

Replace `test_verify_checks_package_and_marketplace_entries` with:

```python
def test_verify_checks_package_and_marketplace_catalogs(tmp_path: Path) -> None:
    install = run_installer(["install", *common_args(tmp_path), "--target", "all", "--scope", "all", "--authorize-install"])
    assert install.returncode == 0, install.stdout + install.stderr

    verify = run_installer(["verify", *common_args(tmp_path), "--target", "all", "--scope", "all"])

    assert verify.returncode == 0, verify.stdout + verify.stderr
    assert "status: verified" in verify.stdout
    assert "source_package: complete" in verify.stdout
    assert "codex_repo_marketplace_entry: present" in verify.stdout
    assert "claude_repo_marketplace_entry: present" in verify.stdout
    assert "codex_personal_marketplace_entry: present" in verify.stdout
    assert "claude_personal_marketplace_entry: present" in verify.stdout


def test_verify_rejects_legacy_marketplace_entry(tmp_path: Path) -> None:
    legacy = tmp_path / "repo-marketplace" / ".agents" / "plugins" / "marketplace.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_text(
        json.dumps({"plugins": [{"name": "agent-guard", "kind": "codex", "install_path": "old"}]}, indent=2) + "\n",
        encoding="utf-8",
    )

    verify = run_installer(["verify", *common_args(tmp_path), "--target", "codex", "--scope", "repo"])

    assert verify.returncode == 1
    assert "legacy_marketplace_entry" in verify.stdout
```

- [x] **Step 6: Run red tests**

Run:

```powershell
python -m pytest tests/test_agent_guard_plugin_installer.py -q
```

Expected: tests fail because `--scope`, new catalog paths, and new entry validation are not implemented yet.

## Task 2: Add Repo Marketplace Catalog Package Tests

**Files:**
- Modify: `tests/test_agent_guard_plugin_package.py`
- Create: `.agents/plugins/marketplace.json`
- Create: `.claude-plugin/marketplace.json`

- [ ] **Step 1: Add catalog path constants**

Add near the existing constants:

```python
CODEX_REPO_MARKETPLACE = REPO_ROOT / ".agents" / "plugins" / "marketplace.json"
CLAUDE_REPO_MARKETPLACE = REPO_ROOT / ".claude-plugin" / "marketplace.json"
```

- [ ] **Step 2: Add package tests for Codex and Claude catalogs**

Add:

```python
def test_repo_marketplace_catalogs_point_to_agent_guard_plugin() -> None:
    codex = read_json(CODEX_REPO_MARKETPLACE)
    claude = read_json(CLAUDE_REPO_MARKETPLACE)

    codex_entry = next(entry for entry in codex["plugins"] if entry["name"] == "agent-guard")
    claude_entry = next(entry for entry in claude["plugins"] if entry["name"] == "agent-guard")

    assert codex["name"] == "agent-guard-marketplace"
    assert codex["interface"]["displayName"] == "Agent Guard"
    assert codex_entry["source"] == {"source": "local", "path": "./plugins/agent-guard"}
    assert codex_entry["policy"] == {"installation": "AVAILABLE", "authentication": "ON_INSTALL"}
    assert codex_entry["category"] == "Productivity"

    assert claude["name"] == "agent-guard-marketplace"
    assert claude["owner"]["name"] == "Agent Guard"
    assert claude_entry["source"] == "./plugins/agent-guard"
    assert claude_entry["description"]
```

- [ ] **Step 3: Add self-contained package boundary test**

Add:

```python
def test_plugin_package_does_not_depend_on_legacy_install_scripts() -> None:
    for legacy_script in [
        REPO_ROOT / "scripts" / "install" / "install_user_skill.ps1",
        REPO_ROOT / "scripts" / "install" / "sync_claude_junction.ps1",
        REPO_ROOT / "scripts" / "install" / "verify_install.py",
    ]:
        assert not legacy_script.exists()
```

- [ ] **Step 4: Create repo catalog files**

Create `.agents/plugins/marketplace.json`:

```json
{
  "name": "agent-guard-marketplace",
  "interface": {
    "displayName": "Agent Guard"
  },
  "plugins": [
    {
      "name": "agent-guard",
      "source": {
        "source": "local",
        "path": "./plugins/agent-guard"
      },
      "policy": {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL"
      },
      "category": "Productivity"
    }
  ]
}
```

Create `.claude-plugin/marketplace.json`:

```json
{
  "name": "agent-guard-marketplace",
  "owner": {
    "name": "Agent Guard"
  },
  "plugins": [
    {
      "name": "agent-guard",
      "source": "./plugins/agent-guard",
      "description": "Guard workflow plugin for Codex and Claude agents"
    }
  ]
}
```

- [ ] **Step 5: Run red package test**

Run:

```powershell
python -m pytest tests/test_agent_guard_plugin_package.py -q
```

Expected: the new legacy-script absence test fails until Task 4 deletes old scripts.

## Task 3: Refactor Installer To Generate And Verify Catalogs

**Files:**
- Modify: `plugins/agent-guard/skills/agent-guard/scripts/install_agent_guard_plugin.py`

- [ ] **Step 1: Add constants and target/scope helpers**

Add:

```python
RELEASE_REF = "marketplace"
CODEX_REPO_MARKETPLACE = REPO_ROOT / ".agents" / "plugins" / "marketplace.json"
CLAUDE_REPO_MARKETPLACE = REPO_ROOT / ".claude-plugin" / "marketplace.json"


def scopes_for(scope: str | None) -> list[str]:
    if scope is None or scope == "all":
        return ["personal", "repo"]
    return [scope]
```

- [ ] **Step 2: Replace old marketplace writer with product-specific catalog builders**

Replace `write_marketplace` and `marketplace_has_entry` with:

```python
def codex_marketplace_entry() -> dict:
    return {
        "name": PLUGIN_NAME,
        "source": {"source": "local", "path": "./plugins/agent-guard"},
        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
        "category": "Productivity",
    }


def claude_marketplace_entry() -> dict:
    return {
        "name": PLUGIN_NAME,
        "source": "./plugins/agent-guard",
        "description": "Guard workflow plugin for Codex and Claude agents",
    }


def write_codex_marketplace(path: Path) -> None:
    write_catalog_entry(
        path,
        root={"name": "agent-guard-marketplace", "interface": {"displayName": "Agent Guard"}, "plugins": []},
        entry=codex_marketplace_entry(),
    )


def write_claude_marketplace(path: Path) -> None:
    write_catalog_entry(
        path,
        root={"name": "agent-guard-marketplace", "owner": {"name": "Agent Guard"}, "plugins": []},
        entry=claude_marketplace_entry(),
    )
```

Also add `write_catalog_entry(path, root, entry)` to read an existing JSON object, replace the `agent-guard` plugin entry, preserve unrelated entries, create parent directories, and write UTF-8 JSON with a trailing newline.

- [ ] **Step 3: Add catalog validation helpers**

Add:

```python
def codex_entry_status(path: Path) -> tuple[str, list[str]]:
    data, error = read_json(path)
    if error is not None:
        return "missing", [error]
    entries = [entry for entry in data.get("plugins", []) if entry.get("name") == PLUGIN_NAME]
    if not entries:
        return "missing", []
    entry = entries[0]
    if "kind" in entry or "install_path" in entry:
        return "legacy", ["legacy_marketplace_entry"]
    expected = codex_marketplace_entry()
    errors = [f"invalid_codex_marketplace_entry: {key}" for key, value in expected.items() if entry.get(key) != value]
    return ("present", []) if not errors else ("invalid", errors)


def claude_entry_status(path: Path) -> tuple[str, list[str]]:
    data, error = read_json(path)
    if error is not None:
        return "missing", [error]
    entries = [entry for entry in data.get("plugins", []) if entry.get("name") == PLUGIN_NAME]
    if not entries:
        return "missing", []
    entry = entries[0]
    expected = claude_marketplace_entry()
    errors = [f"invalid_claude_marketplace_entry: {key}" for key, value in expected.items() if entry.get(key) != value]
    return ("present", []) if not errors else ("invalid", errors)
```

- [ ] **Step 4: Update CLI parser**

Replace old home/marketplace options with:

```python
parser.add_argument("--target", choices=["codex", "claude", "all"], help="安装或验证目标。")
parser.add_argument("--scope", choices=["personal", "repo", "all"], help="marketplace 作用域。")
parser.add_argument("--codex-repo-marketplace", type=Path, default=CODEX_REPO_MARKETPLACE)
parser.add_argument("--claude-repo-marketplace", type=Path, default=CLAUDE_REPO_MARKETPLACE)
parser.add_argument("--codex-personal-marketplace", type=Path, default=default_codex_marketplace())
parser.add_argument("--claude-personal-marketplace", type=Path)
parser.add_argument("--release-ref", default=RELEASE_REF)
parser.add_argument("--authorize-install", action="store_true", help="明确授权写入 marketplace catalog。")
```

Keep unknown `--profile` rejected by argparse.

- [ ] **Step 5: Update dry-run/install/verify orchestration**

Implement these output labels:

```text
status: dry_run
target: all
scope: all
release_ref: marketplace
codex_repo_marketplace: <path>
claude_repo_marketplace: <path>
codex_personal_marketplace: <path>
claude_personal_marketplace: <path>
action: would_update_marketplace_catalogs
```

For `install`, require `--target`, `--scope`, and `--authorize-install`. Write only the selected catalogs. Do not copy plugin packages into `codex_home/plugins` or `claude_home/plugins`.

For `verify`, always run `check_package(args.plugin_source)`, then validate selected catalog entries and print:

```text
codex_repo_marketplace_entry: present
claude_repo_marketplace_entry: present
codex_personal_marketplace_entry: present
claude_personal_marketplace_entry: present
```

- [ ] **Step 6: Run installer tests**

Run:

```powershell
python -m pytest tests/test_agent_guard_plugin_installer.py -q
```

Expected: all installer tests pass.

## Task 4: Remove Legacy User-Level Install Path

**Files:**
- Create: `tests/test_agent_guard_skill_entrypoints.py`
- Delete: `tests/test_user_skill_install.py`
- Delete: `scripts/install/install_user_skill.ps1`
- Delete: `scripts/install/sync_claude_junction.ps1`
- Delete: `scripts/install/verify_install.py`
- Modify or delete: `scripts/install/README.md`

- [ ] **Step 1: Move non-install entrypoint tests**

Create `tests/test_agent_guard_skill_entrypoints.py` with the non-install tests from the old file:

```python
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "agent-guard"
SOURCE_SKILL = PLUGIN_ROOT / "skills" / "agent-guard"
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
```

Copy these existing test bodies into the new file unchanged unless path constants need adjusting:

- `skill_description`
- `test_agent_guard_router_description_covers_routing_triggers`
- `test_agent_guard_router_points_to_scenario_entrypoints`
- `test_scenario_entrypoints_have_strong_required_steps`
- `test_core_references_are_common_and_scenario_docs_live_with_entrypoints`
- `test_templates_do_not_include_python_cache_artifacts`

- [ ] **Step 2: Delete legacy install tests and scripts**

Delete:

```text
tests/test_user_skill_install.py
scripts/install/install_user_skill.ps1
scripts/install/sync_claude_junction.ps1
scripts/install/verify_install.py
```

If `scripts/install/README.md` only documents deleted scripts, delete it. If it also documents marketplace subscription, rewrite it to point to `plugins/agent-guard/skills/agent-guard/scripts/install_agent_guard_plugin.py`.

- [ ] **Step 3: Run moved entrypoint tests**

Run:

```powershell
python -m pytest tests/test_agent_guard_skill_entrypoints.py tests/test_agent_guard_plugin_package.py -q
```

Expected: tests pass after legacy scripts are deleted and catalog files exist.

## Task 5: Update Runtime E2E And Documentation References

**Files:**
- Modify: `tests/test_agent_guard_plugin_runtime_e2e.py`
- Modify: `plugins/agent-guard/skills/agent-guard*/SKILL.md`
- Modify: `plugins/agent-guard/skills/agent-guard*/references/*.md`
- Modify: `openspec/changes/agent-guard-marketplace-subscription/tasks.md`

- [ ] **Step 1: Update runtime e2e installer invocation**

Replace old installer args in `tests/test_agent_guard_plugin_runtime_e2e.py` with:

```python
repo_root = tmp_path / "repo-marketplace"
codex_personal = tmp_path / "codex-personal" / ".agents" / "plugins" / "marketplace.json"
claude_personal = tmp_path / "claude-personal" / ".claude-plugin" / "marketplace.json"
install = run(
    [
        str(INSTALLER),
        "install",
        "--plugin-source",
        str(PLUGIN_ROOT),
        "--target",
        "all",
        "--scope",
        "all",
        "--authorize-install",
        "--codex-repo-marketplace",
        str(repo_root / ".agents" / "plugins" / "marketplace.json"),
        "--claude-repo-marketplace",
        str(repo_root / ".claude-plugin" / "marketplace.json"),
        "--codex-personal-marketplace",
        str(codex_personal),
        "--claude-personal-marketplace",
        str(claude_personal),
    ]
)
```

Apply the same marketplace arguments to the verify call.

- [ ] **Step 2: Replace active documentation references to old install paths**

Scan:

```powershell
rg -n "install_user_skill|sync_claude_junction|verify_install|\\.agents/skills/agent-guard|\\.claude/skills/agent-guard|Claude Junction|user-level Skill" plugins tests scripts docs openspec
```

For active Agent Guard docs, replace old install instructions with marketplace subscription wording:

```text
Codex: codex plugin marketplace add <owner>/<repo> --ref marketplace
Claude: claude plugin marketplace add <owner>/<repo>@marketplace
```

Keep historical OpenSpec archive text unchanged if it is clearly archived context.

- [ ] **Step 3: Check off completed OpenSpec tasks**

As each implementation task passes its focused tests, update `openspec/changes/agent-guard-marketplace-subscription/tasks.md` by changing the matching checkbox from `[ ]` to `[x]`.

- [ ] **Step 4: Run focused verification**

Run:

```powershell
python -m pytest tests/test_agent_guard_plugin_installer.py tests/test_agent_guard_plugin_package.py tests/test_agent_guard_skill_entrypoints.py tests/test_agent_guard_plugin_runtime_e2e.py -q
```

Expected: all selected tests pass.

## Task 6: Final Contract Verification

**Files:**
- Modify: `openspec/changes/agent-guard-marketplace-subscription/tasks.md`

- [ ] **Step 1: Run OpenSpec strict validation**

Run:

```powershell
openspec validate --all --strict --json
```

Expected: all specs pass.

- [ ] **Step 2: Run targeted legacy scan**

Run:

```powershell
rg -n "install_user_skill|sync_claude_junction|verify_install|\\.agents/skills/agent-guard|\\.claude/skills/agent-guard|Claude Junction|user-level Skill" plugins tests scripts docs openspec
```

Expected: no active docs/tests/scripts describe the old user-level Skill installation or Claude Junction as a current Agent Guard publishing contract. If archived OpenSpec context appears, leave it only when the path is clearly archived.

- [ ] **Step 3: Mark OpenSpec tasks complete**

When all focused tests and scans pass, update every applicable checkbox in `openspec/changes/agent-guard-marketplace-subscription/tasks.md` to `[x]`.

- [ ] **Step 4: Commit implementation**

Run:

```powershell
git status --short
git add .agents/plugins/marketplace.json .claude-plugin/marketplace.json plugins/agent-guard/skills/agent-guard/scripts/install_agent_guard_plugin.py tests/test_agent_guard_plugin_installer.py tests/test_agent_guard_plugin_package.py tests/test_agent_guard_plugin_runtime_e2e.py tests/test_agent_guard_skill_entrypoints.py openspec/changes/agent-guard-marketplace-subscription docs/superpowers/specs/2026-06-17-agent-guard-marketplace-subscription-design.md docs/superpowers/plans/2026-06-17-agent-guard-marketplace-subscription.md
git add -u scripts/install tests/test_user_skill_install.py
git commit -m "重构 Agent Guard marketplace 订阅"
```

Expected: commit succeeds after user authorization for commit.

## Self-Review

- Spec coverage: covers marketplace-only publishing, Codex and Claude catalogs, `marketplace` release branch, target/scope separation, legacy user-level Skill removal, safety boundaries, and verification.
- Placeholder scan: no placeholder tokens are present.
- Type consistency: test names, CLI flags, and output labels are consistent across tasks.
