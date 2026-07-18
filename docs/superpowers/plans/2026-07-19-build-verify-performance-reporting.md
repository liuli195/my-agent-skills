---
change: add-build-verify-performance-reporting
design-doc: docs/superpowers/specs/2026-07-19-build-verify-performance-reporting-design.md
base-ref: a6ae972eba609ef3ae71c1e9e51d088cbadccd54
---

# Build and Verify（构建与验证）性能报告 Implementation Plan（实施计划）

> **For agentic workers（面向代理执行者）：** REQUIRED SUB-SKILL（必需子技能）：使用 `superpowers:subagent-driven-development`（子代理驱动开发）或 `superpowers:executing-plans`（执行计划）逐任务实施。

**Goal（目标）：** 为完整验证增加可选总耗时预算、非阻断性能警告和固定 JSON（结构化数据）报告。

**Architecture（架构）：** 复用现有 `CheckResult`（检查结果）和 `_run_scheduled_checks`（运行调度检查）汇总点；`run_verify`（运行验证）仅在 full（完整）模式计时、判断结果完整性和决定是否写报告。报告留在现有运行器文件中，用标准库原子覆盖，不增加模块或依赖。

**Tech Stack（技术栈）：** Python（Python 语言）标准库、pytest（Python 测试框架）、OpenSpec（开放规格）。

## Global Constraints（全局约束）

- `verify.fullBudgetSeconds`（完整验证预算秒数）可选，只接受非布尔正整数，无默认值。
- 完整检查调度结束后才判断预算；性能结果不改变功能退出状态。
- 公开总耗时和逐项耗时统一保留两位小数；预算判断使用公开总耗时。
- 超预算自动写报告；预算内或无预算只在 `--performance-report`（性能报告）存在时写报告。
- 未触发报告、fast verify（快速验证）或结果不完整时，不创建、不覆盖也不删除固定报告。
- 报告固定覆盖 `.build-and-verify/runs/performance-report.json`，只含 `schemaVersion`、`runtimeVersion`、`generatedAt`、`totalSeconds`、`budgetSeconds`、`overBudget`、`verificationStatus` 和 `checks`。
- 不新增模块、依赖、历史文件、逐项预算、基线比较、自动优化或二分定位。
- 不修改根目录 `.build-and-verify/config.json`、CI（持续集成）、安装缓存或用户环境副本。

## Execution Precondition（执行前置条件）

- [ ] **在实现工作区建立前记录全部规划产物**

branch（分支）模式在新分支创建后执行；worktree（独立工作区）模式在创建 worktree 前执行：

```powershell
git add openspec/changes/add-build-verify-performance-reporting docs/superpowers/specs/2026-07-19-build-verify-performance-reporting-design.md docs/superpowers/plans/2026-07-19-build-verify-performance-reporting.md
git commit -m "docs: 记录性能报告变更方案"
```

Expected（预期）：proposal（提案）、design（设计）、delta spec（增量规格）、任务、Design Doc（技术设计文档）和实施计划均进入同一基线提交；执行工作区可读取全部规划产物。

---

### Task 1：实现参数、配置、总计时和报告触发

**Files（文件）：**

- Modify（修改）：`plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py`
- Modify（修改）：`plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify_runner.py`
- Modify（修改）：`tests/test_build_and_verify_plugin.py`

**Interfaces（接口）：**

- `run_verify(project, runner=subprocess.run, *, full=False, performance_report=False, runtime_version="unknown") -> int`
- `_run_scheduled_checks(project, config, selected, changed_files, runner) -> tuple[int, list[str], list[CheckResult]]`
- `_write_performance_report(path, payload) -> bool`

- [ ] **Step 1：写失败测试**

在现有 `tests/test_build_and_verify_plugin.py` 中增加：

1. 参数化拒绝 `True`、`0`、`-1`、`1.5`、`"1"` 作为 `verify.fullBudgetSeconds`，并断言检查命令未运行。
2. `verify --performance-report` 未配合 `--full` 时返回参数错误 2，检查未运行。
3. 使用 fake runner（假执行器）和可控 `time.monotonic()`（单调时钟）覆盖：

| 预算 | 总耗时 | 显式报告 | 功能结果 | 报告 | 警告 | 退出码 |
|---|---:|---|---|---|---|---:|
| 10 | 9.00 | 否 | 通过 | 否 | 否 | 0 |
| 10 | 9.00 | 是 | 通过 | 是 | 否 | 0 |
| 10 | 10.004 | 否 | 通过 | 否 | 否 | 0 |
| 10 | 11.00 | 否 | 通过 | 是 | 是 | 0 |
| 10 | 11.00 | 是 | 失败 | 是 | 是 | 1 |
| 无 | 9.00 | 是 | 通过 | 是 | 否 | 0 |

报告断言至少包含 `budgetSeconds`、`overBudget`、`verificationStatus` 和两位小数的 `totalSeconds`。

- [ ] **Step 2：运行测试并确认失败**

```powershell
python -m pytest tests/test_build_and_verify_plugin.py -k "invalid_full_budget or performance_report_requires_full or full_performance_report_matrix" -q
```

Expected（预期）：失败于新配置、参数或报告行为尚未实现，不得出现测试收集错误。

- [ ] **Step 3：实现最小运行时能力**

在 `build_and_verify.py`：

- 为 `verify`（验证）增加 `--performance-report`。
- 在现有 `SystemExit`（系统退出）捕获范围内拒绝缺少 `--full` 的组合。
- 把 `performance_report` 和 `_runtime_metadata()["runtime_version"]` 传给运行器。
- `RUNTIME_FILES`（运行时文件）保持两个现有脚本。

在 `build_and_verify_runner.py`：

- 在 `_load_config` 中校验 `fullBudgetSeconds`，显式排除布尔值。
- `_run_scheduled_checks` 返回按配置顺序排序的现有结果列表。
- `run_verify` 只在 full（完整）分支用 `time.monotonic()` 包围调度。
- `public_total = round(raw_total, 2)`；只在 `len(results) == len(selected)` 时判断预算和报告触发。
- 每项报告记录固定为：

```python
{
    "id": str(result.check.get("id")),
    "status": "passed" if result.returncode == 0 else "failed",
    "durationSeconds": round(result.duration_seconds, 2),
}
```

- 报告写入同目录 `.performance-report.json.tmp`，再用 `Path.replace`（原子替换）覆盖最终文件；写入失败输出 `performance-report-warning`，返回原功能结果。
- 未触发报告时直接返回，不调用任何删除逻辑。

- [ ] **Step 4：运行聚焦回归**

```powershell
python -m pytest tests/test_build_and_verify_plugin.py -k "invalid_full_budget or performance_report_requires_full or full_performance_report_matrix or runner_build_verify_and_full_verify or full_verify_allows_empty_checks" -q
```

Expected（预期）：全部通过，既有 full（完整）与空检查行为保持不变。

- [ ] **Step 5：提交任务**

```powershell
git add plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify_runner.py tests/test_build_and_verify_plugin.py
git commit -m "feat: 增加完整验证性能报告"
```

---

### Task 2：补齐完整性、schema（结构）和 fast（快速）隔离

**Files（文件）：**

- Modify（修改）：`tests/test_build_and_verify_plugin.py`
- Modify（修改）：`plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify_runner.py`（仅当测试暴露缺口）

**Interfaces（接口）：** 消费 Task 1 的固定报告结构，不增加新类型或状态对象。

- [ ] **Step 1：保留测试辅助类既有语义**

扩展 `FakeRunnerModule.run_verify`（假运行器模块运行验证）时保留原 `_changed_files` 替换和 `finally` 恢复：

```python
def call_runner() -> int:
    return int(
        self.runner_module.run_verify(
            project,
            runner=self.runner,
            full=full,
            performance_report=performance_report,
            runtime_version=runtime_version,
        )
    )

if self.changed_files is None:
    return call_runner()
original_changed_files = self.runner_module._changed_files
self.runner_module._changed_files = lambda _project: list(self.changed_files)
try:
    return call_runner()
finally:
    self.runner_module._changed_files = original_changed_files
```

- [ ] **Step 2：写四个边界测试**

1. `test_build_and_verify_performance_report_schema_is_exact`：用两个检查项断言顶层键集合完全等于八个固定字段、`generatedAt` 以 `Z` 结尾、检查顺序保持配置顺序、每项键集合完全等于 `id`/`status`/`durationSeconds` 且耗时为两位小数；同时扩展现有空检查测试，显式请求报告并断言 `checks == []`。
2. `test_build_and_verify_incomplete_full_results_skip_performance`：两个所选检查只返回一个结果，即使有预算和显式参数，也无性能警告且预置报告内容不变。
3. `test_build_and_verify_fast_verify_leaves_performance_report_unchanged`：配置预算并预置报告，运行 fast verify（快速验证），断言无性能输出且报告字节不变。
4. `test_build_and_verify_report_write_failure_preserves_functional_result`：让临时文件写入抛出 `OSError`，断言输出报告警告但功能成功仍返回 0。

原子替换复用现有 cache（缓存）原子写入测试模式，只增加一个 `Path.replace` 调用断言，不增加独立 writer（写入器）抽象。

- [ ] **Step 3：运行测试并确认先失败后通过**

```powershell
python -m pytest tests/test_build_and_verify_plugin.py -k "performance_report_schema or incomplete_full_results or fast_verify_leaves_performance_report or report_write_failure or performance_report_replaces" -q
```

Expected（预期）：RED（失败）阶段命中新边界；最小修正后 GREEN（通过）。

- [ ] **Step 4：运行现有运行器回归**

```powershell
python -m pytest tests/test_build_and_verify_plugin.py -k "build_and_verify_runner or performance_report or cache_store_writes_temp" -q
```

Expected（预期）：并行、缓存、超时、中断、fast（快速）与 full（完整）相关测试全部通过。

- [ ] **Step 5：提交任务**

```powershell
git add plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify_runner.py tests/test_build_and_verify_plugin.py
git commit -m "test: 完善性能报告运行边界"
```

---

### Task 3：同步 Skill（技能）、初始化闭环和版本

**Files（文件）：**

- Modify（修改）：`plugins/build-and-verify/skills/build-and-verify/SKILL.md`
- Modify（修改）：`plugins/build-and-verify/skills/build-and-verify-init/SKILL.md`
- Modify（修改）：`plugins/build-and-verify/skills/build-and-verify-init/references/questionnaire.md`
- Modify（修改）：`plugins/build-and-verify/skills/build-and-verify-init/references/ecosystem-detection.md`
- Modify（修改）：`plugins/build-and-verify/skills/build-and-verify-init/references/config-draft.md`
- Modify（修改）：`plugins/build-and-verify/skills/build-and-verify-init/references/validation.md`
- Modify（修改）：`plugins/build-and-verify/.codex-plugin/plugin.json`
- Modify（修改）：`plugins/build-and-verify/.claude-plugin/plugin.json`
- Modify（修改）：`tests/test_build_and_verify_plugin.py`

- [ ] **Step 1：写文档与版本契约测试**

断言：

- 运行 Skill（技能）包含预算语义、显式参数、自动报告、固定路径、非阻断说明和“未触发时不修改已有报告”。
- Init Skill（初始化技能）四份引用都包含可选 `verify.fullBudgetSeconds`，只在用户确认正整数后写入；不启用时省略。
- 运行时复制仍只有两个脚本和 `version.json`。
- 双 manifest（清单）版本都为 `0.1.37`，复制出的 `runtime_version` 同步为 `0.1.37`。

- [ ] **Step 2：运行测试并确认失败**

```powershell
python -m pytest tests/test_build_and_verify_plugin.py -k "dual_manifests or runtime_and_init_skill_entrypoints or init_questionnaire or init_config_draft or init_validation or init_copies_repository_runtime" -q
```

- [ ] **Step 3：更新现有文档和双 manifest（清单）**

- Q5 增加启用、修改或保持禁用完整预算；Q6 展示最终值或未启用。
- 已有配置扫描保留该字段；草案无确认不写；写后校验排除布尔值和非正整数。
- 通用模板保持无预算字段。
- 两份 manifest（清单）从 `0.1.36` 更新到 `0.1.37`；不新建源码 `version.json`。

- [ ] **Step 4：运行契约测试确认通过**

```powershell
python -m pytest tests/test_build_and_verify_plugin.py -k "dual_manifests or runtime_and_init_skill_entrypoints or init_references or init_questionnaire or init_config_draft or init_validation or init_copies_repository_runtime" -q
```

- [ ] **Step 5：提交任务**

```powershell
git add plugins/build-and-verify/.codex-plugin/plugin.json plugins/build-and-verify/.claude-plugin/plugin.json plugins/build-and-verify/skills/build-and-verify/SKILL.md plugins/build-and-verify/skills/build-and-verify-init tests/test_build_and_verify_plugin.py
git commit -m "docs: 增加性能预算初始化说明"
```

---

### Task 4：验证复制后运行时的两个发布场景

**Files（文件）：**

- Modify（修改）：`tests/test_build_and_verify_plugin.py`
- Modify（修改）：`tests/test_test_runtime_boundaries.py`

- [ ] **Step 1：写一个临时目标仓库 E2E（端到端测试）**

从插件源码入口执行 `init`（初始化）复制实际运行时，然后在同一临时仓库依次验证：

1. 配置预算 1 秒；第一个通用 Python（Python 语言）检查等待 1.05 秒，第二个检查写出标记；运行 `verify --full`，断言两个检查都完成、自动报告生成、`overBudget is True`、退出码为 0。
2. 改为无预算的快速通用检查；运行 `verify --full --performance-report`，断言固定报告被覆盖、`budgetSeconds is None`、`overBudget is None`、退出码为 0。

该测试不调用本仓库业务检查。功能失败且超预算的退出码组合继续由 Task 1 进程内矩阵验证，避免第二次真实等待。

- [ ] **Step 2：精确登记 E2E allowlist（端到端允许清单）**

只增加测试函数 identity（标识）及“复制后 full verify（完整验证）性能报告入口”理由，同步现有精确身份列表；不放宽扫描规则。

- [ ] **Step 3：运行发布形态与边界测试**

```powershell
python -m pytest tests/test_build_and_verify_plugin.py::test_copied_runtime_full_performance_report_e2e_temp_target_repo tests/test_test_runtime_boundaries.py::test_e2e_allowlist_entries_match_current_runtime_hits tests/test_test_runtime_boundaries.py::test_build_and_verify_keeps_focused_real_entrypoint_coverage -q
```

Expected（预期）：三个测试通过，真实等待只发生一次。

- [ ] **Step 4：提交任务**

```powershell
git add tests/test_build_and_verify_plugin.py tests/test_test_runtime_boundaries.py
git commit -m "test: 验证复制运行时性能报告"
```

---

### Task 5：完成规格与主流程验证

**Files（文件）：**

- Modify（修改）：`openspec/changes/add-build-verify-performance-reporting/tasks.md`（仅在证据通过后勾选）

- [ ] **Step 1：运行插件测试与格式检查**

```powershell
git diff --check
python -m pytest tests/test_build_and_verify_plugin.py tests/test_test_runtime_boundaries.py -q
```

- [ ] **Step 2：运行 OpenSpec（开放规格）严格校验**

```powershell
openspec validate add-build-verify-performance-reporting --strict --no-interactive
```

- [ ] **Step 3：运行仓库 build/fast/full（构建/快速/完整）主流程**

不修改根目录业务配置：

```powershell
python plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py build --project .
python plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py verify --project .
python plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py verify --project . --full
```

Expected（预期）：三条命令都返回 0。

- [ ] **Step 4：复核范围并完成任务勾选**

```powershell
git diff --name-only a6ae972eba609ef3ae71c1e9e51d088cbadccd54..HEAD
git status --short
```

确认没有根目录 `.build-and-verify/config.json`、CI（持续集成）、安装缓存或用户环境副本进入差异；逐项勾选 `tasks.md`。

- [ ] **Step 5：提交验证记录**

```powershell
git add openspec/changes/add-build-verify-performance-reporting/tasks.md
git commit -m "test: 完成性能报告变更验证"
```

## Coverage Map（覆盖映射）

| 要求 | 任务 |
|---|---|
| 总预算、全部运行后警告、功能退出状态权威 | Task 1 |
| 固定 schema（结构）、结果完整性、fast（快速）隔离、写入失败 | Task 2 |
| Skill（技能）、初始化和运行时版本契约 | Task 3 |
| 超预算自动报告与预算内显式报告的发布形态入口 | Task 4 |
| OpenSpec（开放规格）、插件和仓库主流程验证 | Task 5 |
