---
change: add-build-and-verify-init-skill
design-doc: docs/superpowers/specs/2026-06-26-build-and-verify-init-skill-design.md
base-ref: d6a1ca3c11e7648678a68186fe76f4ada92a1342
archived-with: 2026-06-26-add-build-and-verify-init-skill
---

# Build and Verify Init Skill（构建与验证初始化技能）实施计划

> **For agentic workers（给代理工作者）:** REQUIRED SUB-SKILL（必需子技能）: Use `superpowers:subagent-driven-development`（子代理驱动开发，推荐） or `superpowers:executing-plans`（执行计划） to implement（实施） this plan（计划） task-by-task（逐任务执行）. Steps（步骤） use checkbox（复选框） `- [x]` syntax（语法） for tracking（跟踪）.

**Goal（目标）:** 新增独立 `build-and-verify-init`（构建与验证初始化）Skill（技能），用固定模板引导 agent（代理）为通用仓库生成可审查的 `.build-and-verify/config.json`（配置文件）。

**Architecture（架构）:** 保持现有 `build-and-verify`（构建与验证）Skill（技能）和命令行 `init`（初始化）不变；新增一个只负责对话式初始化的 Skill（技能）目录。所有可变细节放入 `references/`（参考文件）并由测试锁定：问答、生态识别、配置草案、依赖/环境检查和配置校验。

**Tech Stack（技术栈）:** Markdown（标记文档）、Python（Python 语言）、pytest（Python 测试运行器）、OpenSpec（开放规格）、build-and-verify runner（构建与验证运行器）。

archived-with: 2026-06-26-add-build-and-verify-init-skill
---

## File Map（文件清单）

- Modify（修改）: `tests/test_build_and_verify_plugin.py`，更新插件入口、命令行 `init`（初始化）和模板完整性测试。
- Create（新建）: `plugins/build-and-verify/skills/build-and-verify-init/SKILL.md`，新增初始化向导 Skill（技能）入口。
- Create（新建）: `plugins/build-and-verify/skills/build-and-verify-init/references/questionnaire.md`，固定问答模板。
- Create（新建）: `plugins/build-and-verify/skills/build-and-verify-init/references/ecosystem-detection.md`，Node（节点运行时）和 Python（Python 语言）识别规则。
- Create（新建）: `plugins/build-and-verify/skills/build-and-verify-init/references/config-draft.md`，配置草案规则。
- Create（新建）: `plugins/build-and-verify/skills/build-and-verify-init/references/validation.md`，定向依赖检查、环境检查和结构校验规则。
- Verify（验证）: `openspec/changes/add-build-and-verify-init-skill/tasks.md`，实现完成后由执行者勾选已完成项。

## Task 1: 测试先行，锁定双 Skill（技能）入口

**Files（文件）:**
- Modify（修改）: `tests/test_build_and_verify_plugin.py`

- [x] **Step 1: Add（新增）初始化 Skill（技能）常量**

在 `PLUGIN_NAME`（插件名）常量下方加入：

```python
INIT_SKILL_NAME = "build-and-verify-init"
INIT_SKILL_ROOT = PLUGIN_ROOT / "skills" / INIT_SKILL_NAME
INIT_REFERENCE_ROOT = INIT_SKILL_ROOT / "references"
REQUIRED_INIT_REFERENCES = {
    "questionnaire.md",
    "ecosystem-detection.md",
    "config-draft.md",
    "validation.md",
}
```

- [x] **Step 2: Replace（替换）单入口测试为双入口测试**

将 `test_build_and_verify_plugin_has_single_skill_entrypoint` 改名为 `test_build_and_verify_plugin_has_runtime_and_init_skill_entrypoints`，并替换函数体：

```python
def test_build_and_verify_plugin_has_runtime_and_init_skill_entrypoints() -> None:
    skill_root = PLUGIN_ROOT / "skills"
    runtime_script_path = skill_root / PLUGIN_NAME / "scripts" / "build_and_verify.py"
    skill_dirs = sorted(path.name for path in skill_root.iterdir() if path.is_dir())
    runtime_skill_text = (skill_root / PLUGIN_NAME / "SKILL.md").read_text(encoding="utf-8")
    runtime_front_matter = runtime_skill_text.split("---", 2)[1]
    init_skill_text = (INIT_SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    init_front_matter = init_skill_text.split("---", 2)[1]

    assert skill_dirs == [PLUGIN_NAME, INIT_SKILL_NAME]
    assert runtime_script_path.is_file()
    assert runtime_skill_text.startswith("---\n")
    assert f"name: {PLUGIN_NAME}" in runtime_front_matter
    assert "本仓库 build（构建检查）和 verify（验证）的统一入口" in runtime_skill_text
    assert "默认 verify（验证）使用 fast（快速）模式" in runtime_skill_text
    assert "`--full`（完整）只允许 PR Flow hotfix（拉取请求流程热修复）直推流程和 PR CI（拉取请求持续集成）使用" in runtime_skill_text
    assert "不安装依赖" in runtime_skill_text
    assert "不写用户级配置" in runtime_skill_text
    assert "不配置 CI（持续集成）" in runtime_skill_text
    assert "不内置仓库业务逻辑" in runtime_skill_text
    assert "不向目标仓库复制 runner（运行器）" in runtime_skill_text
    assert "scripts/build_and_verify.py init" in runtime_skill_text
    assert "scripts/build_and_verify.py build" in runtime_skill_text
    assert "scripts/build_and_verify.py verify" in runtime_skill_text
    assert "timeoutSeconds" in runtime_skill_text
    assert "pytest-xdist" in runtime_skill_text

    assert init_skill_text.startswith("---\n")
    assert f"name: {INIT_SKILL_NAME}" in init_front_matter
    assert "questionnaire.md" in init_skill_text
    assert "ecosystem-detection.md" in init_skill_text
    assert "config-draft.md" in init_skill_text
    assert "validation.md" in init_skill_text
    assert "用户沉默不能视为确认" in init_skill_text
    assert "不新增命令行初始化脚本" in init_skill_text
    assert "不安装依赖" in init_skill_text
    assert "不写用户级配置" in init_skill_text
    assert "不配置 CI（持续集成）" in init_skill_text
```

- [x] **Step 3: Run（运行）入口测试确认先失败**

Run（运行）:

```powershell
python -m pytest -q tests/test_build_and_verify_plugin.py::test_build_and_verify_plugin_has_runtime_and_init_skill_entrypoints
```

Expected（预期）: FAIL（失败），原因是 `plugins/build-and-verify/skills/build-and-verify-init/SKILL.md` 尚不存在。

## Task 2: 测试先行，保护命令行 init（初始化）不变

**Files（文件）:**
- Modify（修改）: `tests/test_build_and_verify_plugin.py`

- [x] **Step 1: Strengthen（增强）现有 init（初始化）测试**

在 `test_build_and_verify_init_writes_config_gitignore_and_cache` 末尾追加这些断言：

```python
    assert "build-and-verify-init" not in result.stdout
    assert "questionnaire" not in result.stdout.lower()
    assert "questionnaire" not in result.stderr.lower()
    assert not (project / ".build-and-verify" / "backups").exists()
    assert read_json(project / ".build-and-verify" / "config.json")["build"]["checks"] == []
    assert read_json(project / ".build-and-verify" / "config.json")["verify"]["checks"] == []
```

- [x] **Step 2: Run（运行）init（初始化）回归测试**

Run（运行）:

```powershell
python -m pytest -q tests/test_build_and_verify_plugin.py::test_build_and_verify_init_writes_config_gitignore_and_cache tests/test_build_and_verify_plugin.py::test_build_and_verify_init_refuses_existing_files_before_writes
```

Expected（预期）: PASS（通过）。如果失败，说明本轮之外已有行为漂移，先定位漂移原因，不改 `build_and_verify.py`（构建与验证脚本）来适配新 Skill（技能）。

## Task 3: 测试先行，锁定 reference（参考文件）完整性

**Files（文件）:**
- Modify（修改）: `tests/test_build_and_verify_plugin.py`

- [x] **Step 1: Add（新增）reference（参考文件）存在性测试**

在 Skill（技能）入口测试后加入：

```python
def test_build_and_verify_init_references_all_required_files() -> None:
    assert INIT_SKILL_ROOT.is_dir()
    assert INIT_REFERENCE_ROOT.is_dir()
    assert {
        path.name for path in INIT_REFERENCE_ROOT.iterdir() if path.is_file()
    } == REQUIRED_INIT_REFERENCES
```

- [x] **Step 2: Add（新增）questionnaire（问答模板）完整性测试**

加入：

```python
def test_build_and_verify_init_questionnaire_contains_fixed_flow() -> None:
    text = (INIT_REFERENCE_ROOT / "questionnaire.md").read_text(encoding="utf-8")
    required_questions = [
        "Q1 目标仓库路径确认",
        "Q2 扫描授权",
        "Q3 检测结果确认",
        "Q4 check（检查项）选择",
        "Q5 paths（受影响路径）确认",
        "Q6 inputs（缓存输入）确认",
        "Q7 并行和超时确认",
        "Q8 覆盖确认",
        "Q9 备份路径确认",
        "Q10 最终写入确认",
    ]

    for question in required_questions:
        assert question in text
    assert "固定选项" in text
    assert "选择后果" in text
    assert "跳转规则" in text
    assert "用户沉默不能视为确认" in text
```

- [x] **Step 3: Add（新增）ecosystem（生态）识别测试**

加入：

```python
def test_build_and_verify_init_ecosystem_detection_covers_node_python_and_fallback() -> None:
    text = (INIT_REFERENCE_ROOT / "ecosystem-detection.md").read_text(encoding="utf-8")

    for token in [
        "package.json",
        "scripts",
        "build",
        "test",
        "lint",
        "typecheck",
        "pyproject.toml",
        "pytest.ini",
        "tox.ini",
        "noxfile.py",
        "requirements*.txt",
        "未识别生态",
        "手动提供 build（构建检查）和 verify（验证）命令",
    ]:
        assert token in text
```

- [x] **Step 4: Add（新增）config-draft（配置草案）测试**

加入：

```python
def test_build_and_verify_init_config_draft_rules_cover_commands_paths_inputs_and_runtime_tuning() -> None:
    text = (INIT_REFERENCE_ROOT / "config-draft.md").read_text(encoding="utf-8")

    for token in [
        "build.checks",
        "verify.checks",
        "check id（检查项标识）",
        "短横线",
        "command（命令）默认使用字符串形式",
        "列表形式 command（命令）只在用户明确要求",
        "paths（受影响路径）",
        "inputs（缓存输入）",
        "verify.maxParallel",
        "verify.timeoutSeconds",
        "parallel: true",
        "auto（自动）语义",
    ]:
        assert token in text
```

- [x] **Step 5: Add（新增）validation（校验）测试**

加入：

```python
def test_build_and_verify_init_validation_rules_cover_dependency_backup_and_dry_run() -> None:
    text = (INIT_REFERENCE_ROOT / "validation.md").read_text(encoding="utf-8")

    for token in [
        "targeted dependency checks（定向依赖检查）",
        "pytest-xdist",
        "可执行入口",
        "缺失文件或目录",
        "不安装依赖",
        ".build-and-verify/backups/config-YYYYMMDD-HHMMSS.json",
        "/backups/",
        "config（配置）结构校验",
        "build（构建检查）",
        "默认 verify（快速验证）",
        "environment checks（环境检查）",
    ]:
        assert token in text
```

- [x] **Step 6: Add（新增）OpenSpec（开放规格）delta spec（规格增量）锚点测试**

加入：

```python
def test_build_and_verify_init_delta_spec_targets_test_framework_plugin_capability() -> None:
    spec_path = (
        REPO_ROOT
        / "openspec"
        / "changes"
        / "add-build-and-verify-init-skill"
        / "specs"
        / "test-framework-plugin"
        / "spec.md"
    )
    text = spec_path.read_text(encoding="utf-8")

    assert "Runtime and initialization skill surfaces" in text
    assert "build-and-verify-init" in text
    assert "template-driven guided initialization" in text
    assert "Guided initialization validates config and environment before completion" in text
```

- [x] **Step 7: Run（运行）新增完整性测试确认先失败**

Run（运行）:

```powershell
python -m pytest -q tests/test_build_and_verify_plugin.py -k "init_references or init_questionnaire or init_ecosystem or init_config_draft or init_validation or init_delta_spec"
```

Expected（预期）: FAIL（失败），原因是新 Skill（技能）和 reference（参考文件）尚不存在。

## Task 4: 新增 build-and-verify-init（构建与验证初始化）Skill（技能）入口

**Files（文件）:**
- Create（新建）: `plugins/build-and-verify/skills/build-and-verify-init/SKILL.md`

- [x] **Step 1: Create（新建）Skill（技能）说明**

写入完整内容：

```markdown
archived-with: 2026-06-26-add-build-and-verify-init-skill
---
name: build-and-verify-init
description: Build and Verify（构建与验证）对话式初始化向导；为目标仓库生成 .build-and-verify/config.json（配置文件）草案
archived-with: 2026-06-26-add-build-and-verify-init-skill
---

# Build and Verify Init（构建与验证初始化）

Use this skill when the user asks to initialize（初始化）, generate（生成）, draft（草拟）, or configure（配置） `.build-and-verify/config.json`（配置文件） for a target repository（目标仓库）.

## Hard Boundaries（硬边界）

- 不新增命令行初始化脚本；`build-and-verify`（构建与验证）现有 `scripts/build_and_verify.py init`（初始化命令）仍只写空模板。
- 不安装依赖。
- 不写用户级配置。
- 不配置 CI（持续集成）。
- 不修改 runner（运行器）语义。
- 用户沉默不能视为确认。
- 覆盖已有 `.build-and-verify/config.json`（配置文件）前必须展示摘要、等待明确确认并备份。
- 处理依赖或环境问题前必须获得用户明确授权。

## Required Flow（必需流程）

1. 先读取 `references/questionnaire.md`（问答模板），并按固定问题、固定选项、选择后果和跳转规则推进。
2. 用户允许扫描后，读取 `references/ecosystem-detection.md`（生态识别规则），只识别 Node（节点运行时）和 Python（Python 语言）；未识别时走手动命令分支。
3. 生成草案前，读取 `references/config-draft.md`（配置草案规则），按其中规则生成 `build.checks`（构建检查项）和 `verify.checks`（验证检查项）。
4. 最终写入确认前，读取 `references/validation.md`（校验规则），执行 targeted dependency checks（定向依赖检查）并展示问题、影响和建议。
5. 写入后按 `references/validation.md`（校验规则）执行 config（配置）结构校验。

## Output（输出）

- 写入前输出候选 checks（检查项）、`paths`（受影响路径）、`inputs`（缓存输入）、运行参数、覆盖摘要、备份路径和定向依赖检查结果。
- 写入后输出配置路径、备份路径和结构校验结果。
- 如发现依赖或环境问题，明确说明用户可以让 agent（代理）协助处理环境和外部依赖问题；处理前必须获得用户明确授权。
```

- [x] **Step 2: Run（运行）入口测试**

Run（运行）:

```powershell
python -m pytest -q tests/test_build_and_verify_plugin.py::test_build_and_verify_plugin_has_runtime_and_init_skill_entrypoints
```

Expected（预期）: FAIL（失败），原因是 reference（参考文件）还未创建。

## Task 5: 新增 questionnaire（问答模板）reference（参考文件）

**Files（文件）:**
- Create（新建）: `plugins/build-and-verify/skills/build-and-verify-init/references/questionnaire.md`

- [x] **Step 1: Create（新建）固定问答模板**

写入完整内容：

```markdown
# Questionnaire（问答模板）

本文件定义 `build-and-verify-init`（构建与验证初始化）必须使用的固定问题。agent（代理）不得自由编造初始化问题，不得跳过 Q10 最终写入确认。用户沉默不能视为确认。

每个问题必须向用户展示固定选项、选择后果和跳转规则。

## Q1 目标仓库路径确认

- 固定选项：
  - 使用当前目录。
  - 使用用户提供的绝对路径。
  - 停止初始化。
- 选择后果：
  - 使用当前目录：后续扫描、备份和写入都以当前目录为目标仓库。
  - 使用用户提供的绝对路径：先确认路径存在且是目录。
  - 停止初始化：不读取、不写入目标仓库。
- 跳转规则：确认路径后进入 Q2；停止时结束流程。

## Q2 扫描授权

- 固定选项：
  - 允许扫描仓库文件。
  - 不允许扫描，改为手动提供命令。
  - 停止初始化。
- 选择后果：
  - 允许扫描：读取 ecosystem-detection（生态识别）允许的文件。
  - 不允许扫描：跳过生态识别，在 Q4 手动填写候选 checks（检查项）。
  - 停止初始化：不写入配置。
- 跳转规则：允许扫描进入 Q3；不允许扫描进入 Q4 的手动分支。

## Q3 检测结果确认

- 固定选项：
  - 接受检测结果。
  - 修改检测结果。
  - 改为手动提供命令。
  - 停止初始化。
- 选择后果：
  - 接受检测结果：把候选 Node（节点运行时）和 Python（Python 语言）checks（检查项）带入 Q4。
  - 修改检测结果：用户可删除误判生态或补充遗漏生态。
  - 改为手动提供命令：不使用自动候选命令。
  - 停止初始化：不写入配置。
- 跳转规则：确认后进入 Q4。

## Q4 check（检查项）选择

- 固定选项：
  - 纳入全部候选 checks（检查项）。
  - 只纳入用户选择的 checks（检查项）。
  - 手动新增 checks（检查项）。
  - 返回 Q3。
  - 停止初始化。
- 选择后果：
  - 纳入全部候选：所有候选命令进入配置草案。
  - 只纳入用户选择：未选择项不会写入配置。
  - 手动新增：用户提供 check id（检查项标识）和 command（命令）。
  - 返回 Q3：重新确认检测结果。
- 跳转规则：至少有一个 build（构建检查）或 verify（验证）候选后进入 Q5；如果用户选择空配置，仍可继续但必须说明不会产生业务检查项。

## Q5 paths（受影响路径）确认

- 固定选项：
  - 接受建议 paths（受影响路径）。
  - 修改 paths（受影响路径）。
  - 为某些 verify checks（验证检查项）移除 paths（受影响路径），使其成为 global check（全局检查项）。
  - 返回 Q4。
  - 停止初始化。
- 选择后果：
  - 接受建议：默认 verify（快速验证）按变更文件选择检查项。
  - 修改：使用用户确认后的路径模式。
  - 移除 paths：该 verify check（验证检查项）在有任意 changed file（变更文件）时被选择。
- 跳转规则：确认后进入 Q6。

## Q6 inputs（缓存输入）确认

- 固定选项：
  - 接受建议 inputs（缓存输入）。
  - 修改 inputs（缓存输入）。
  - 对某些 checks（检查项）移除 inputs（缓存输入）。
  - 返回 Q5。
  - 停止初始化。
- 选择后果：
  - 接受建议：cache key（缓存键）使用明确输入。
  - 修改：使用用户确认后的输入。
  - 移除 inputs：runner（运行器）按自身规则计算 cache key（缓存键），大型仓库可能更慢。
- 跳转规则：确认后进入 Q7。

## Q7 并行和超时确认

- 固定选项：
  - 接受建议运行参数。
  - 修改 `verify.maxParallel`（最大并行检查数）。
  - 修改 `verify.timeoutSeconds`（超时秒数）。
  - 修改单个 check（检查项）的 `parallel: true`（并行检查）。
  - 返回 Q6。
  - 停止初始化。
- 选择后果：
  - 接受建议：写入已解释的运行参数。
  - 修改：只写入用户确认的数值或布尔值。
  - 未确认：不写入对应运行参数。
- 跳转规则：确认后检查目标仓库是否已有 `.build-and-verify/config.json`（配置文件）；存在则进入 Q8，不存在则进入 Q10。

## Q8 覆盖确认

- 固定选项：
  - 新建配置，不覆盖已有配置。
  - 覆盖已有 `.build-and-verify/config.json`（配置文件）。
  - 返回 Q7。
  - 停止初始化。
- 选择后果：
  - 新建配置：如果配置已存在，必须停止并说明原因。
  - 覆盖已有配置：进入 Q9 确认备份路径。
  - 返回 Q7：重新确认运行参数。
- 跳转规则：新建且目标不存在时进入 Q10；覆盖时进入 Q9。

## Q9 备份路径确认

- 固定选项：
  - 接受 `.build-and-verify/backups/config-YYYYMMDD-HHMMSS.json`（备份配置文件）。
  - 修改备份路径。
  - 返回 Q8。
  - 停止初始化。
- 选择后果：
  - 接受默认备份：覆盖前复制旧配置，并确保 `.build-and-verify/.gitignore`（忽略规则）包含 `/backups/`。
  - 修改备份路径：必须仍在目标仓库内，且不得覆盖已有文件。
  - 返回 Q8：重新选择覆盖策略。
- 跳转规则：确认备份后进入 Q10。

## Q10 最终写入确认

- 固定选项：
  - 确认写入。
  - 返回前面问题修改草案。
  - 取消，不写入。
- 选择后果：
  - 确认写入：先展示 targeted dependency checks（定向依赖检查）结果和 environment checks（环境检查）结果；如用户继续，则备份旧配置、写入新配置并做结构校验。
  - 返回修改：按用户指定问题返回。
  - 取消：不写入配置。
- 跳转规则：确认写入前必须展示完整草案、覆盖摘要、备份路径、依赖检查结果、环境检查结果和写入后配置校验计划。
```

- [x] **Step 2: Run（运行）问答模板测试**

Run（运行）:

```powershell
python -m pytest -q tests/test_build_and_verify_plugin.py::test_build_and_verify_init_questionnaire_contains_fixed_flow
```

Expected（预期）: PASS（通过）。

## Task 6: 新增 ecosystem-detection（生态识别）reference（参考文件）

**Files（文件）:**
- Create（新建）: `plugins/build-and-verify/skills/build-and-verify-init/references/ecosystem-detection.md`

- [x] **Step 1: Create（新建）生态识别规则**

写入完整内容：

```markdown
# Ecosystem Detection（生态识别）

本文件只允许识别 Node（节点运行时）和 Python（Python 语言）。混合仓库必须同时展示两类候选 checks（检查项），不得自动裁决优先级。

## Scan Boundary（扫描边界）

- 只在用户授权扫描后读取目标仓库文件。
- 不安装依赖，不运行 package manager（包管理器），不修改文件。
- 只读取本文件列出的生态信号。

## Node（节点运行时）

检测信号：

- `package.json`（包配置）存在。

读取规则：

- 读取 `package.json`（包配置）的 `scripts`（脚本）对象。
- 识别 `build`、`test`、`lint`、`typecheck`、`check`、`verify` 等脚本名。
- 用包管理器命令展示候选 command（命令）。如果存在 lockfile（锁文件），按下列顺序建议：
  - `pnpm-lock.yaml` -> `pnpm <script>`
  - `yarn.lock` -> `yarn <script>`
  - `package-lock.json` -> `npm run <script>`
  - 无 lockfile（锁文件） -> `npm run <script>`
- 只使用第一个匹配的 lockfile（锁文件）选择包管理器；如果多个 lockfile（锁文件）同时存在，必须展示冲突并让用户选择一个包管理器，不得同时生成多个互相冲突的 command（命令）。

候选映射：

- `build` -> `build.node`
- `test` -> `verify.node-tests`
- `lint` -> `verify.node-lint`
- `typecheck` -> `verify.node-typecheck`
- `check` -> `verify.node-check`
- `verify` -> `verify.node-verify`

展示要求：

- 展示脚本名、原始 script（脚本）内容、建议 check id（检查项标识）和建议 command（命令）。
- 等待用户选择纳入哪些 checks（检查项）。

## Python（Python 语言）

检测信号：

- `pyproject.toml`（项目配置）
- `pytest.ini`（测试配置）
- `tox.ini`（测试环境配置）
- `noxfile.py`（任务配置）
- `requirements*.txt`（依赖清单）

读取规则：

- 优先识别 pytest（Python 测试运行器）：存在 `pytest.ini`（测试配置）、`pyproject.toml`（项目配置）中包含 pytest（Python 测试运行器）配置、或 `requirements*.txt`（依赖清单）包含 `pytest`。
- 如果存在 `tox.ini`（测试环境配置），展示 `tox`（测试环境工具）候选，但不替代 pytest（Python 测试运行器）候选。
- 如果存在 `noxfile.py`（任务配置），展示 `nox`（自动化任务工具）候选，但不替代 pytest（Python 测试运行器）候选。

候选映射：

- pytest（Python 测试运行器） -> `verify.python-tests`，默认 command（命令）为 `python -m pytest`
- tox（测试环境工具） -> `verify.python-tox`，默认 command（命令）为 `tox`
- nox（自动化任务工具） -> `verify.python-nox`，默认 command（命令）为 `nox`

展示要求：

- 展示检测到的配置文件、建议 check id（检查项标识）和建议 command（命令）。
- 等待用户选择纳入哪些 checks（检查项）。

## Mixed Repository（混合仓库）

- Node（节点运行时）和 Python（Python 语言）信号同时存在时，同时展示两类候选 checks（检查项）。
- 不根据文件数量、语言比例或 agent（代理）偏好自动删减候选项。
- 由用户选择纳入哪些 checks（检查项）。

## 未识别生态

如果没有识别到 Node（节点运行时）或 Python（Python 语言）信号：

- 继续使用 questionnaire（问答模板）。
- 让用户手动提供 build（构建检查）和 verify（验证）命令。
- 继续确认 paths（受影响路径）、inputs（缓存输入）、覆盖备份和 config validation（配置校验）。
```

- [x] **Step 2: Run（运行）生态识别测试**

Run（运行）:

```powershell
python -m pytest -q tests/test_build_and_verify_plugin.py::test_build_and_verify_init_ecosystem_detection_covers_node_python_and_fallback
```

Expected（预期）: PASS（通过）。

## Task 7: 新增 config-draft（配置草案）reference（参考文件）

**Files（文件）:**
- Create（新建）: `plugins/build-and-verify/skills/build-and-verify-init/references/config-draft.md`

- [x] **Step 1: Create（新建）配置草案规则**

写入完整内容：

````markdown
# Config Draft（配置草案）

本文件定义 `.build-and-verify/config.json`（配置文件）草案生成规则。草案必须可审查，写入前必须展示给用户确认。

## Shape（结构）

草案默认使用：

```json
{
  "version": 1,
  "build": {
    "checks": []
  },
  "verify": {
    "checks": []
  }
}
```

## Checks（检查项）

- 必须同时支持 `build.checks`（构建检查项）和 `verify.checks`（验证检查项）。
- check id（检查项标识）使用短横线风格，例如 `build.node`、`verify.node-tests`、`verify.python-tests`。
- 同一分组内 check id（检查项标识）必须唯一。
- command（命令）默认使用字符串形式，便于用户阅读和维护。
- 列表形式 command（命令）只在用户明确要求更稳定参数边界时使用。

## Node（节点运行时）建议

- `build.node`
  - command（命令）: `npm run build`、`pnpm build` 或 `yarn build`
  - inputs（缓存输入）: `package.json`、lockfile（锁文件）、源码目录
- `verify.node-tests`
  - command（命令）: `npm test`、`pnpm test` 或 `yarn test`
  - paths（受影响路径）: `src/**`、`test/**`、`tests/**`、`package.json`
  - inputs（缓存输入）: `package.json`、lockfile（锁文件）、源码目录、测试目录
- `verify.node-lint`
  - command（命令）: `npm run lint`、`pnpm lint` 或 `yarn lint`
  - paths（受影响路径）: `src/**`、配置文件和脚本文件
  - inputs（缓存输入）: `package.json`、lockfile（锁文件）、lint（代码检查）配置
- `verify.node-typecheck`
  - command（命令）: `npm run typecheck`、`pnpm typecheck` 或 `yarn typecheck`
  - paths（受影响路径）: `src/**`、`tsconfig.json`
  - inputs（缓存输入）: `package.json`、lockfile（锁文件）、`tsconfig.json`、源码目录

## Python（Python 语言）建议

- `verify.python-tests`
  - command（命令）: `python -m pytest`
  - paths（受影响路径）: `src/**`、`tests/**`、`pyproject.toml`、`pytest.ini`
  - inputs（缓存输入）: `pyproject.toml`、`pytest.ini`、`requirements*.txt`、源码目录、测试目录
- `verify.python-tox`
  - command（命令）: `tox`
  - paths（受影响路径）: `src/**`、`tests/**`、`tox.ini`
  - inputs（缓存输入）: `tox.ini`、`pyproject.toml`、`requirements*.txt`、源码目录、测试目录
- `verify.python-nox`
  - command（命令）: `nox`
  - paths（受影响路径）: `src/**`、`tests/**`、`noxfile.py`
  - inputs（缓存输入）: `noxfile.py`、`pyproject.toml`、`requirements*.txt`、源码目录、测试目录

## paths（受影响路径）

- verify checks（验证检查项）应建议 paths（受影响路径）。
- 写入前必须逐项展示 paths（受影响路径）并等待用户确认。
- 用户可以移除 paths（受影响路径），使该 verify check（验证检查项）成为 global check（全局检查项）。

## inputs（缓存输入）

- 每个 check（检查项）都应建议 inputs（缓存输入），以降低 cache key（缓存键）不稳定风险。
- 写入前必须逐项展示 inputs（缓存输入）并等待用户确认。
- 指向不存在文件或目录时，在 validation（校验）阶段提示用户确认。

## Runtime Tuning（运行参数）

- `verify.maxParallel`（最大并行检查数）只能在解释含义并获得用户确认后写入。
- `verify.timeoutSeconds`（超时秒数）只能在解释含义并获得用户确认后写入。
- `parallel: true`（并行检查）只能在解释 runner（运行器）并行语义并获得用户确认后写入。
- 并行默认推荐 auto（自动）语义；如果某个工具没有 auto（自动）语义，不能硬编码 auto（自动）参数。
````

- [x] **Step 2: Run（运行）配置草案测试**

Run（运行）:

```powershell
python -m pytest -q tests/test_build_and_verify_plugin.py::test_build_and_verify_init_config_draft_rules_cover_commands_paths_inputs_and_runtime_tuning
```

Expected（预期）: PASS（通过）。

## Task 8: 新增 validation（校验）reference（参考文件）

**Files（文件）:**
- Create（新建）: `plugins/build-and-verify/skills/build-and-verify-init/references/validation.md`

- [x] **Step 1: Create（新建）校验规则**

写入完整内容：

```markdown
# Validation（校验）

本文件定义写入前和写入后的检查顺序。检查发现问题时仍允许用户继续写入配置，但必须列明问题、影响和建议。agent（代理）不得未经授权安装依赖或修改外部环境。

## Order（顺序）

1. 写入前执行 targeted dependency checks（定向依赖检查）。
2. 用户最终确认后，必要时备份已有配置。
3. 写入 `.build-and-verify/config.json`（配置文件）。
4. 写入后执行 config（配置）结构校验。
5. 写入后执行 config（配置）结构校验。

## Targeted Dependency Checks（定向依赖检查）

- command（命令）包含 `pytest -n`、`-n` pytest（Python 测试运行器）参数或 `--numprocesses` 时，检查 `pytest-xdist`（Pytest 并行插件）是否可用。
- command（命令）调用外部可执行入口时，检查该可执行入口是否可找到。
- paths（受影响路径）或 inputs（缓存输入）指向缺失文件或目录时，提示用户确认。
- `parallel: true`（并行检查）只说明 build-and-verify（构建与验证）runner（运行器）支持并行执行，不推断业务依赖。

报告格式必须包含：

- 问题。
- 影响。
- 建议。
- 是否阻止写入：默认不阻止，除非用户要求停止。

## Backup（备份）

覆盖已有 `.build-and-verify/config.json`（配置文件）前必须：

- 复制旧配置到 `.build-and-verify/backups/config-YYYYMMDD-HHMMSS.json`（备份配置文件）。
- 确保 `.build-and-verify/.gitignore`（忽略规则）包含 `/backups/`。
- 在写入结果中报告备份路径。

## Config Structure Validation（配置结构校验）

写入后必须确认 `.build-and-verify/config.json`（配置文件）符合 runner（运行器）契约：

- 顶层是 object（对象）。
- `build.checks`（构建检查项）和 `verify.checks`（验证检查项）是 list（清单）。
- 每个 check（检查项）有非空且同分组唯一的 `id`（标识）。
- 每个 check（检查项）有非空 string（字符串）或 string list（字符串清单）形式的 command（命令）。
- `paths`（受影响路径）和 `inputs`（缓存输入）如果存在，必须是非空 string list（字符串清单）。
- `verify.maxParallel`（最大并行检查数）如果存在，必须是非负整数。

## Environment Checks（环境检查）

- 确认目标仓库路径存在且是目录。
- 确认 `.build-and-verify`（配置目录）可创建或可写入。
- 覆盖已有配置时，确认备份目录可创建且备份路径仍在目标仓库内。
- 发现依赖或环境问题时，必须明确说明用户可以让 agent（代理）协助处理环境和外部依赖问题，但处理前必须获得用户明确授权。
```

- [x] **Step 2: Run（运行）校验测试**

Run（运行）:

```powershell
python -m pytest -q tests/test_build_and_verify_plugin.py::test_build_and_verify_init_validation_rules_cover_dependency_backup_and_dry_run
```

Expected（预期）: PASS（通过）。

## Task 9: 集中运行模板和入口测试

**Files（文件）:**
- Modify（修改）: `tests/test_build_and_verify_plugin.py`
- Create（新建）: `plugins/build-and-verify/skills/build-and-verify-init/SKILL.md`
- Create（新建）: `plugins/build-and-verify/skills/build-and-verify-init/references/questionnaire.md`
- Create（新建）: `plugins/build-and-verify/skills/build-and-verify-init/references/ecosystem-detection.md`
- Create（新建）: `plugins/build-and-verify/skills/build-and-verify-init/references/config-draft.md`
- Create（新建）: `plugins/build-and-verify/skills/build-and-verify-init/references/validation.md`

- [x] **Step 1: Run（运行）聚焦测试**

Run（运行）:

```powershell
python -m pytest -q tests/test_build_and_verify_plugin.py -k "skill_entrypoints or init_references or init_questionnaire or init_ecosystem or init_config_draft or init_validation or init_delta_spec or init_writes_config_gitignore_and_cache or init_refuses_existing_files"
```

Expected（预期）: PASS（通过）。

- [x] **Step 2: Run（运行）完整 build-and-verify（构建与验证）插件测试**

Run（运行）:

```powershell
python -m pytest -q tests/test_build_and_verify_plugin.py
```

Expected（预期）: PASS（通过）。

## Task 10: OpenSpec（开放规格）和仓库验证

**Files（文件）:**
- Verify（验证）: `openspec/changes/add-build-and-verify-init-skill/tasks.md`
- Verify（验证）: `.build-and-verify/config.json`

- [x] **Step 1: Run（运行）OpenSpec（开放规格）严格校验**

Run（运行）:

```powershell
openspec validate add-build-and-verify-init-skill --strict --no-interactive
```

Expected（预期）: PASS（通过）。

- [x] **Step 2: Run（运行）默认 verify（快速验证）**

Run（运行）:

```powershell
python plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py verify --project .
```

Expected（预期）: PASS（通过）。不要默认运行 `--full`（完整验证）。

- [x] **Step 3: Update（更新）OpenSpec（开放规格）tasks（任务）清单**

实现者确认上面验证通过后，在 `openspec/changes/add-build-and-verify-init-skill/tasks.md` 中勾选本次完成项：

```markdown
- [x] 1.1 Update build-and-verify（构建与验证）package tests so the plugin exposes both `build-and-verify`（运行入口） and `build-and-verify-init`（初始化向导入口） Skill（技能） directories.
- [x] 1.2 Update tests that currently assert a single Skill（技能） entrypoint so they assert the new two-entrypoint contract.
- [x] 1.3 Add tests proving command-line `init`（初始化） still writes the empty template config, `.gitignore`（忽略规则）, and `cache`（缓存） directory without interactive behavior.
- [x] 1.4 Add OpenSpec（开放规格） validation coverage for the `test-framework-plugin`（测试框架插件） delta spec（规格增量）.
- [x] 2.1 Create `plugins/build-and-verify/skills/build-and-verify-init/SKILL.md`（技能说明）, with concise routing instructions and progressive disclosure（渐进式披露） links.
- [x] 2.2 Create `references/questionnaire.md`（问答模板） with fixed questions, fixed options, consequence notes, and jump rules.
- [x] 2.3 Create `references/ecosystem-detection.md`（生态识别规则） for Node（节点运行时） and Python（Python 语言） repository detection.
- [x] 2.4 Create `references/ecosystem-detection.md`（生态识别规则） fallback guidance for repositories without recognized Node（节点运行时） or Python（Python 语言） signals.
- [x] 2.5 Create `references/config-draft.md`（配置草案规则） for check id（检查项标识）, default string command（字符串命令）, paths（受影响路径）, inputs（缓存输入）, timeout（超时）, and parallel（并行） settings.
- [x] 2.6 Create `references/validation.md`（校验规则） for pre-write targeted dependency checks（写入前定向依赖检查）, environment checks（环境检查）, and post-write config（配置） structure validation.
- [x] 3.1 Add tests that `build-and-verify-init`（构建与验证初始化） references all required reference（参考） files.
- [x] 3.2 Add tests that `questionnaire.md`（问答模板） contains all 10 required initialization questions: target path, scan authorization, detection confirmation, check（检查项） selection, paths（受影响路径）, inputs（缓存输入）, parallel/timeout（并行/超时）, overwrite（覆盖）, backup path（备份路径）, and final write confirmation.
- [x] 3.3 Add tests that `validation.md`（校验规则） includes `pytest-xdist`（Pytest 并行插件） detection, executable lookup, missing path reporting, and no unauthorized dependency installation.
- [x] 3.4 Add tests that `config-draft.md`（配置草案规则） requires default string command（字符串命令）, with list command（列表命令） only after explicit user request for stricter argument boundaries.
- [x] 3.5 Add tests that `config-draft.md`（配置草案规则） requires user confirmation for `verify.maxParallel`（最大并行检查数）, `verify.timeoutSeconds`（超时秒数）, and `parallel: true`（并行检查）.
- [x] 3.6 Add tests that backup behavior requires `.build-and-verify/backups/config-YYYYMMDD-HHMMSS.json`（备份配置文件） and `/backups/` in `.build-and-verify/.gitignore`（忽略规则）.
- [x] 3.7 Add tests that no recognized ecosystem（未识别生态） fallback still collects user-provided commands through the fixed questionnaire（问答模板）.
- [x] 3.8 Add tests that initialization references do not require command execution after writing config（配置）.
- [x] 4.1 Run focused build-and-verify（构建与验证） tests covering plugin package, init（初始化）, and template integrity.
- [x] 4.2 Run `openspec validate add-build-and-verify-init-skill --strict --no-interactive`.
- [x] 4.3 Run default build-and-verify（构建与验证） `verify`（快速验证） for this repository without `--full`（完整验证）.
```

- [x] **Step 4: Prepare（准备）实现总结**

最终实现总结必须包含：

```markdown
Implemented（已实现）:
- 新增 `build-and-verify-init`（构建与验证初始化）Skill（技能）。
- 新增 questionnaire（问答模板）、ecosystem-detection（生态识别）、config-draft（配置草案）和 validation（校验）reference（参考文件）。
- 保持命令行 `init`（初始化）只写空模板、`.gitignore`（忽略规则）和 `cache`（缓存）目录。

Verified（已验证）:
- `python -m pytest -q tests/test_build_and_verify_plugin.py`
- `openspec validate add-build-and-verify-init-skill --strict --no-interactive`
- `python plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py verify --project .`
```

## Self-Review（自查）

- Spec coverage（规格覆盖）: 计划覆盖双 Skill（技能）入口、固定问答、progressive disclosure（渐进式披露）reference（参考文件）、Node（节点运行时）/Python（Python 语言）识别、未识别生态分支、配置草案、覆盖备份、定向依赖检查、环境检查、结构校验和命令行 `init`（初始化）不变。
- Placeholder scan（占位扫描）: 本计划不使用未定义占位项；每个新增文件都有完整建议内容，每个测试步骤都有具体断言和命令。
- Type consistency（类型一致性）: 测试常量、Skill（技能）目录名、reference（参考文件）文件名和 OpenSpec（开放规格）change（变更）名保持一致。
