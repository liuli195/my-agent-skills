---
change: simplify-pr-flow-review-gate
design-doc: docs/superpowers/specs/2026-06-30-simplify-pr-flow-review-gate-design.md
base-ref: ad44a774e0eb2ffbd87f9bb550c2ea482b88d038
---

# Simplify PR Flow Review Gate Implementation Plan

> **For agentic workers（代理执行者）:** REQUIRED SUB-SKILL（必需子技能）: Use superpowers:subagent-driven-development（子代理驱动开发） or superpowers:executing-plans（执行计划） to implement this plan task-by-task（逐项执行）. Steps use checkbox（复选框） syntax（语法） for tracking（跟踪）.

**Goal（目标）:** 把 PR Flow（拉取请求流程）review gate（审查门禁）收敛到 `github`（GitHub 审查）和 `skip`（跳过），删除旧本地 evidence（证据）路径。

**Architecture（结构）:** 先用测试锁住 validate（校验）、complete（收尾）和 init（初始化）文档契约，再做最小实现。运行时只保留 GitHub（代码托管平台）审查和跳过两条分支；init（初始化）继续由 branch protection（分支保护）选择派生模式。

**Tech Stack（技术栈）:** Python（编程语言）、pytest（测试工具）、OpenSpec（开放规格）、Markdown（文档格式）、YAML（配置格式）。

---

## File Map（文件地图）

- Modify（修改）: `tests/test_pr_flow_cli.py`（测试 PR Flow 命令行）
  - 覆盖 validate（校验）只接受 `github`（GitHub 审查）/`skip`（跳过），拒绝 `local`（本地）/`dual`（双重）。
  - 覆盖 complete（收尾）只处理 `github`（GitHub 审查）/`skip`（跳过），不再读取 `.pr-flow/review-pass.json`（审查通过文件）。
  - 覆盖 init（初始化）参考文档中 branch protection（分支保护）派生 `github`（GitHub 审查）/`skip`（跳过）。
- Modify（修改）: `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`
  - 删除或停用本地 evidence（证据）读取、diff fingerprint（差异指纹）计算和本地 evidence（证据）比较。
  - 更新 `validate_config`（校验配置）、`default_config`（默认配置）和 `check_review_gate`（检查审查门禁）。
- Modify（修改）: `plugins/pr-flow/skills/pr-flow-init/references/questionnaire.md`
  - branch protection（分支保护）选择一个或多个分支时派生 `github`（GitHub 审查）。
  - 选择暂不配置远端保护时派生 `skip`（跳过）。
- Modify（修改）: `plugins/pr-flow/skills/pr-flow-init/references/config-draft.md`
  - 删除保持旧默认值的描述，改为 `github`（GitHub 审查）/`skip`（跳过）派生规则。
- Modify（修改）: `openspec/specs/pr-flow-plugin/spec.md`
  - 将主规格同步为两种 review gate（审查门禁）模式，并删除 `Cross-agent-review evidence generation`（跨代理审查证据生成）要求。

不安排 git commit（提交）；执行者完成后只运行验证并汇报。

---

### Task 1: Validate（校验）模式收敛测试

**Files（文件）:**
- Modify（修改）: `tests/test_pr_flow_cli.py`

- [x] **Step 1: 写失败测试**

在现有 validate（校验）测试附近替换本地 evidence（证据）相关测试，保留现有 helper（辅助函数）即可。

```python
@pytest.mark.parametrize("review_mode", ["github", "skip"])
def test_validate_accepts_supported_review_gate_modes(tmp_path: Path, review_mode: str) -> None:
    config = default_pr_flow_config_for_test()
    config["defaults"]["reviewGate"] = {"mode": review_mode}
    draft = tmp_path / "draft.yaml"
    draft.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")

    result = run("validate", "--config", str(draft))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: validation_passed" in result.stdout
    assert "defaults.reviewGate.evidencePath" not in result.stdout
    assert "review-pass.json" not in result.stdout


@pytest.mark.parametrize("review_mode", ["local", "dual"])
def test_validate_rejects_removed_review_gate_modes(tmp_path: Path, review_mode: str) -> None:
    config = default_pr_flow_config_for_test()
    config["defaults"]["reviewGate"] = {"mode": review_mode, "evidencePath": ".pr-flow/review-pass.json"}
    draft = tmp_path / "draft.yaml"
    draft.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")

    result = run("validate", "--config", str(draft))

    assert result.returncode == 1
    assert "status: validation_failed" in result.stdout
    assert f"error: defaults.reviewGate.mode unsupported: {review_mode}" in result.stdout
    assert "document review-pass.json evidence contract" not in result.stdout
    assert "defaults.reviewGate.evidencePath missing" not in result.stdout
```

把 `test_validate_reports_errors_for_missing_core_shape`（缺少核心结构校验测试）里的期望从 `defaults.reviewGate.evidencePath missing` 改成 `defaults.reviewGate.mode unsupported: local`。

把 `test_validate_dependency_matrix`（依赖矩阵校验测试）中 `reviewGate: local` 的用例期望改成：

```python
"error: defaults.reviewGate.mode unsupported: local"
```

- [x] **Step 2: 运行测试确认失败**

Run（运行）:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_pr_flow_cli.py -k "validate and review_gate" -q
```

Expected（预期）: 新增测试失败，因为当前 `local`（本地）/`dual`（双重）仍被接受，且默认配置仍写入 `evidencePath`（证据路径）。

---

### Task 2: Complete（收尾）门禁行为测试

**Files（文件）:**
- Modify（修改）: `tests/test_pr_flow_cli.py`

- [x] **Step 1: 写失败测试**

把 `write_complete_pr_flow_config`（写收尾配置辅助函数）默认 review gate（审查门禁）改为不写 `evidencePath`（证据路径），并让 `run_complete_in_process`（进程内运行收尾辅助函数）接收 `review_mode`（审查模式）。

```python
def write_complete_pr_flow_config(
    project: Path,
    *,
    review_mode: str = "github",
    merge_strategy: str = "merge",
    evidence_path: str | None = None,
) -> None:
    config_dir = project / ".pr-flow"
    config_dir.mkdir(parents=True, exist_ok=True)
    review_gate = {"mode": review_mode}
    if evidence_path is not None:
        review_gate["evidencePath"] = evidence_path
    config = {
        "defaults": {
            "baseBranch": "main",
            "mergeStrategy": merge_strategy,
            "reviewGate": review_gate,
            "wait": {"timeoutSeconds": 0, "pollSeconds": 0},
        },
        "branches": {"main": {"remote": "origin"}},
    }
    (config_dir / "config.yaml").write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
```

在 `run_complete_in_process`（进程内运行收尾辅助函数）参数中加入：

```python
review_mode: str = "github",
```

并把写配置调用改成：

```python
write_complete_pr_flow_config(project, merge_strategy=merge_strategy, review_mode=review_mode)
```

新增测试：

```python
def test_complete_skip_review_gate_ignores_blocking_github_review(tmp_path: Path, monkeypatch) -> None:
    result_project, result = run_complete_in_process(
        tmp_path,
        monkeypatch,
        review_mode="skip",
        pr_stdout=pr_view_json(
            checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}],
            review_decision="CHANGES_REQUESTED",
            head_oid="b" * 40,
        ),
        cleanup_stdout=cleanup_pr_view_json(),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: merge_complete" in result.stdout
    assert not (result_project / ".pr-flow" / "review-pass.json").exists()


def test_complete_github_review_gate_still_blocks_changes_requested(tmp_path: Path, monkeypatch) -> None:
    project, result = run_complete_in_process(
        tmp_path,
        monkeypatch,
        review_mode="github",
        pr_stdout=pr_view_json(
            checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}],
            review_decision="CHANGES_REQUESTED",
            head_oid="b" * 40,
        ),
    )

    assert result.returncode == 1
    assert "status: REPLY_OR_FIX_REQUIRED" in result.stdout
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["details"]["reason"] == "review_gate_blocking"
    assert status["details"]["reviewGateMode"] == "github"
```

删除或改写依赖 `write_review_pass`（写审查通过文件）、`write_review_pass_file`（写审查通过文件）和 `diff_fingerprint`（差异指纹）的 local/dual（本地/双重）complete（收尾）测试；这些契约在本变更中移除。

- [x] **Step 2: 运行测试确认失败**

Run（运行）:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_pr_flow_cli.py -k "complete and review_gate" -q
```

Expected（预期）: `skip`（跳过）用例应暴露当前代码仍保留本地 evidence（证据）分支或 helper（辅助函数）仍默认写旧字段。

---

### Task 3: Init（初始化）文档派生规则测试

**Files（文件）:**
- Modify（修改）: `tests/test_pr_flow_cli.py`

- [x] **Step 1: 写失败测试**

更新 `test_init_creates_config_template_and_gitignore`（初始化创建配置模板与忽略文件测试）：

```python
assert config["defaults"]["reviewGate"]["mode"] == "github"
assert "evidencePath" not in config["defaults"]["reviewGate"]
```

更新 `test_pr_flow_init_questionnaire_uses_latest_flow`（初始化问答使用最新流程测试）中 branch protection（分支保护）断言：

```python
assert "defaults.reviewGate.mode: github" in branch_protection_section
assert "defaults.reviewGate.mode: skip" in branch_protection_section
assert "暂不配置远端保护" in branch_protection_section
assert "保持现有或默认 `reviewGate.mode` 不变" not in branch_protection_section
assert "不得派生 `defaults.reviewGate.mode: github`" not in branch_protection_section
```

更新 `test_pr_flow_init_draft_and_validation_are_user_readable`（初始化草案和校验用户可读测试）：

```python
assert "defaults.reviewGate.mode" in config_draft
assert "不单独提问" in config_draft
assert "选择暂不配置远端保护时派生为 `skip`" in config_draft
assert "选择暂不配置远端保护时保持现有或默认值不变" not in config_draft
```

- [x] **Step 2: 运行测试确认失败**

Run（运行）:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_pr_flow_cli.py -k "init and reviewGate or questionnaire or draft" -q
```

Expected（预期）: 失败点应集中在默认 `evidencePath`（证据路径）和“保持现有或默认值不变”的旧文案。

---

### Task 4: 最小运行时实现

**Files（文件）:**
- Modify（修改）: `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`

- [x] **Step 1: 更新默认配置**

把 `default_config`（默认配置）里的 review gate（审查门禁）改成：

```python
"reviewGate": {"mode": "github"},
```

- [x] **Step 2: 更新 validate_config（校验配置）**

将 review gate（审查门禁）校验逻辑收敛为：

```python
review_gate = defaults.get("reviewGate")
review_gate = review_gate if isinstance(review_gate, dict) else {}
review_mode = review_gate.get("mode", "github")
if review_mode not in {"skip", "github"}:
    add_issue(issues, "error", f"defaults.reviewGate.mode unsupported: {review_mode}")
if review_mode == "github":
    add_issue(issues, "remote task", "configure GitHub required review")
```

不要再检查 `defaults.reviewGate.evidencePath`（证据路径），不要再输出 `document review-pass.json evidence contract`（记录审查通过文件契约）。

- [x] **Step 3: 删除或停用本地 evidence（证据）函数**

删除下列函数及只服务于它们的 import（导入）：

```python
load_local_review_evidence
current_diff_fingerprint
local_review_evidence_passes
```

如果删除 `current_diff_fingerprint`（当前差异指纹）后 `hashlib`（哈希库）没有其他用途，也删除 `import hashlib`。

- [x] **Step 4: 更新 check_review_gate（检查审查门禁）**

把 `check_review_gate`（检查审查门禁）改成只处理 `skip`（跳过）和 `github`（GitHub 审查）：

```python
def check_review_gate(project: Path, config: dict[str, Any], pr: dict[str, Any]) -> dict[str, Any] | None:
    mode = review_gate_mode(config)
    details = {
        "reason": "review_gate_blocking",
        "reviewGateMode": mode,
        "reviewDecision": pr.get("reviewDecision"),
        "pr": pr.get("number"),
        "headRefName": pr.get("headRefName"),
        "baseRefName": pr.get("baseRefName"),
    }
    if mode == "skip":
        return None
    if mode != "github":
        details["reason"] = "unknown_review_gate_mode"
        return stop_state("EXCEPTION_REQUIRED", "unknown_review_gate_mode", details)
    if github_review_is_blocking(pr):
        return stop_state("REPLY_OR_FIX_REQUIRED", "review_gate_blocking", details)
    return None
```

- [x] **Step 5: 运行聚焦测试**

Run（运行）:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_pr_flow_cli.py -k "validate or complete or init" -q
```

Expected（预期）: Task 1-3（任务 1-3）新增和改写测试通过。

---

### Task 5: Init（初始化）参考文档与主规格

**Files（文件）:**
- Modify（修改）: `plugins/pr-flow/skills/pr-flow-init/references/questionnaire.md`
- Modify（修改）: `plugins/pr-flow/skills/pr-flow-init/references/config-draft.md`
- Modify（修改）: `openspec/specs/pr-flow-plugin/spec.md`

- [x] **Step 1: 更新 questionnaire.md（问答模板）**

在 branch protection（分支保护）场景的选择后果中保留保护分支派生 `github`（GitHub 审查），并把暂不配置远端保护改成：

```markdown
- 选择“暂不配置远端保护”时，派生写入 `defaults.reviewGate.mode: skip`，表示 PR Flow（拉取请求流程）跳过 review gate（审查门禁），只依赖 checks（检查）和后续合并约束。
```

删除旧句：

```markdown
- 选择“暂不配置远端保护”时，不得派生 `defaults.reviewGate.mode: github`；保持现有或默认 `reviewGate.mode` 不变。
```

- [x] **Step 2: 更新 config-draft.md（配置草案文档）**

把关键字段路径中的 `defaults.reviewGate.mode`（审查门禁模式）说明改成：

```markdown
- `defaults.reviewGate.mode`：由 branch protection（分支保护）选择派生，不单独提问；选择一个或多个保护分支时派生为 `github`，选择暂不配置远端保护时派生为 `skip`。
```

- [x] **Step 3: 更新主规格 spec.md（规格文档）**

将 `Requirement: Review gate modes`（审查门禁模式要求）替换为：

```markdown
### Requirement: Review gate modes
系统 MUST 只支持 GitHub（代码托管平台）和 skip（跳过）两种 review gate（审查门禁）模式。

#### Scenario: GitHub review gate
- **WHEN** `reviewGate.mode` 为 `github`
- **THEN** 系统 MUST 读取 PR（拉取请求）的 `reviewDecision`（审查结论）
- **THEN** 系统 MUST 在 `CHANGES_REQUESTED`（要求修改）或 `REVIEW_REQUIRED`（需要审查）时阻止合并

#### Scenario: Skipped review gate
- **WHEN** `reviewGate.mode` 为 `skip`
- **THEN** 系统 MUST 跳过 review gate（审查门禁）
- **THEN** 系统 MUST NOT 读取本地 review evidence（审查证据）

#### Scenario: Unsupported review gate modes
- **WHEN** `reviewGate.mode` 为 `local`、`dual` 或其他非支持值
- **THEN** validate（校验） MUST 报告 unsupported review gate mode（不支持的审查门禁模式）
- **THEN** complete（收尾） MUST NOT treat that mode as local review evidence（本地审查证据）
```

删除 `Requirement: Cross-agent-review evidence generation`（跨代理审查证据生成要求）整段。

把 `Complete path does not force full verification`（收尾路径不强制完整验证）里的 local evidence（本地证据）句子改成：

```markdown
- **THEN** review gate（审查门禁） mode（模式） MUST NOT be treated as a request to run full verify（完整验证）
```

把 `Unknown verification mode is not inferred`（未知验证模式不被推断）里的 evidence（证据）表述改成：

```markdown
- **WHEN** PR Flow（拉取请求流程） consumes review gate（审查门禁） mode（模式） or check status（检查状态）
```

- [x] **Step 4: 运行文档相关测试**

Run（运行）:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_pr_flow_cli.py -k "init or validate" -q
```

Expected（预期）: init（初始化）文档断言和 validate（校验）断言通过。

---

### Task 6: OpenSpec（开放规格）与必要构建验证

**Files（文件）:**
- No file edits（不改文件）

- [x] **Step 1: 运行聚焦 pytest（测试工具）**

Run（运行）:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_pr_flow_cli.py -q
```

Expected（预期）: `tests/test_pr_flow_cli.py` 全部通过。

- [x] **Step 2: 运行 OpenSpec strict validate（开放规格严格校验）**

Run（运行）:

```powershell
openspec validate simplify-pr-flow-review-gate --strict
```

Expected（预期）: 输出通过；如果命令不可用，改用仓库现有 OpenSpec（开放规格）入口，但必须保留 `--strict`（严格）语义。

- [x] **Step 3: 运行必要构建验证**

优先运行仓库当前快速验证入口：

```powershell
.\.venv\Scripts\python.exe plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py verify --project .
```

Expected（预期）: 快速验证通过。只有在 PR（拉取请求）准备或仓库规则要求完整验证时，再运行显式 full verify（完整验证）：

```powershell
.\.venv\Scripts\python.exe plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py verify --project . --full
```

---

## Self-Review（自查）

- Spec coverage（规格覆盖）: validate（校验）、complete（收尾）、init（初始化）派生规则、本地 evidence（证据）删除、主规格同步和验证命令都有对应任务。
- Placeholder scan（占位扫描）: 没有 TBD（待定）、TODO（待办）或空泛“补测试”步骤；每个代码变更步骤都有可执行片段。
- YAGNI（不做未需功能）: 不桥接 `cross-agent-review`（跨代理审查），不新增 init（初始化）问题，不新增依赖，不新增 GitHub API（GitHub 接口）调用。
