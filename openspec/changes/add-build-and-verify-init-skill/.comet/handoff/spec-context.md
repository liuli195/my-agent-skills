# Comet Spec Context

- Change: add-build-and-verify-init-skill
- Phase: design
- Mode: beta
- Context hash: 20432dd3b844469882436c891cdd950fd7e31cf523461efefa3c4cf61d9781d7

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This beta context pack verbatim-projects spec files and references supporting artifacts by hash, not an agent-authored summary.

## Source References

- Source: openspec/changes/add-build-and-verify-init-skill/proposal.md
- SHA256: f66f78dce76e8ae77683d0763eec340123c1484cb3d613a32d7f58b4c4b11c5a
- Source: openspec/changes/add-build-and-verify-init-skill/design.md
- SHA256: ae046b015aa62e4f417bea7f8a602a8151b1cafc7bb53c309c256edb11eef592
- Source: openspec/changes/add-build-and-verify-init-skill/tasks.md
- SHA256: e33dc91308b2cc304d353071db3fa1fa77eaa18640dbd70526e816616bf6558d
- Source: openspec/changes/add-build-and-verify-init-skill/specs/test-framework-plugin/spec.md
- SHA256: 5de8ef7d18267ea2c85ee1c828da77419d98a637385d2d41aec5fae1f741e04f

## Acceptance Projection

## openspec/changes/add-build-and-verify-init-skill/specs/test-framework-plugin/spec.md

- Source: openspec/changes/add-build-and-verify-init-skill/specs/test-framework-plugin/spec.md
- Lines: 1-130
- SHA256: 5de8ef7d18267ea2c85ee1c828da77419d98a637385d2d41aec5fae1f741e04f

```md
## MODIFIED Requirements

### Requirement: Build and Verify plugin package supports Claude and Codex
系统 MUST 提供轻量 `build-and-verify` Plugin（构建与验证插件），同一套能力 MUST 同时面向 Claude（Claude 版本）和 Codex（Codex 版本）。

#### Scenario: Codex plugin structure
- **WHEN** 发布 `build-and-verify` Plugin（插件）
- **THEN** 插件包 MUST 包含 `.codex-plugin/plugin.json`
- **THEN** Codex manifest（清单） MUST 声明插件 `name`、`version`、`description` 和 `skills`

#### Scenario: Claude plugin structure
- **WHEN** 发布 `build-and-verify` Plugin（插件）
- **THEN** 插件包 MUST 包含 `.claude-plugin/plugin.json`
- **THEN** Claude manifest（清单） MUST 声明插件 `name`、`version`、`description` 和 `skills`

#### Scenario: Runtime and initialization skill surfaces
- **WHEN** 安装 `build-and-verify` Plugin（插件）
- **THEN** 插件包 MUST 提供 `build-and-verify` Skill（构建与验证技能）作为运行入口
- **THEN** 插件包 MUST 提供 `build-and-verify-init` Skill（构建与验证初始化技能）作为对话式初始化向导入口
- **THEN** `build-and-verify` Skill（技能） MUST 调用共享确定性脚本，而不是复制多套流程逻辑
- **THEN** `build-and-verify-init` Skill（技能） MUST 使用参考文件表达固定初始化流程，而不是新增命令行初始化脚本

## ADDED Requirements

### Requirement: Build and Verify provides template-driven guided initialization
系统 MUST 通过 `build-and-verify-init` Skill（构建与验证初始化技能）提供模板化对话式初始化向导，用于为通用仓库生成 `.build-and-verify/config.json`（配置文件）。

#### Scenario: Guided initialization uses fixed questionnaire
- **WHEN** agent（代理）使用 `build-and-verify-init` Skill（构建与验证初始化技能）
- **THEN** Skill（技能） MUST 指示 agent（代理）读取固定 questionnaire（问答模板）
- **THEN** questionnaire（问答模板） MUST 定义固定问题、固定选项、后果说明和跳转规则
- **THEN** questionnaire（问答模板） MUST 覆盖目标仓库路径确认、扫描授权、检测结果确认、check（检查项）选择、`paths`（受影响路径）确认、`inputs`（缓存输入）确认、并行与超时确认、覆盖确认、备份路径确认、dry run（试运行）范围选择和最终写入确认
- **THEN** agent（代理） MUST NOT 自由编造初始化问题或跳过最终写入确认

#### Scenario: Guided initialization uses progressive disclosure references
- **WHEN** 发布 `build-and-verify-init` Skill（构建与验证初始化技能）
- **THEN** Skill（技能） MUST 将固定问答模板放在独立 reference（参考文件）
- **THEN** Skill（技能） MUST 将 Node（节点运行时）和 Python（Python 语言）识别规则放在独立 reference（参考文件）
- **THEN** Skill（技能） MUST 将配置草案规则放在独立 reference（参考文件）
- **THEN** Skill（技能） MUST 将校验和试运行规则放在独立 reference（参考文件）

#### Scenario: Guided initialization keeps command-line init unchanged
- **WHEN** 用户运行 `python <build-and-verify-script> init --project <repo>`
- **THEN** 系统 MUST 保持现有命令行 init（初始化）行为
- **THEN** 系统 MUST 创建空的 `.build-and-verify/config.json`（配置文件）模板
- **THEN** 系统 MUST NOT 在命令行 init（初始化）中执行对话式问答
- **THEN** 系统 MUST NOT 在命令行 init（初始化）中自动生成仓库业务检查项

### Requirement: Guided initialization drafts generic repository checks
`build-and-verify-init` Skill（构建与验证初始化技能） MUST 为通用仓库生成可审查的 build（构建检查）和 verify（验证）配置草案。

#### Scenario: Node repository detection
- **WHEN** 目标仓库包含 `package.json`（包配置）
- **THEN** agent（代理） MUST 读取 `scripts`（脚本）并识别 build、test、lint 和 typecheck 等候选命令
- **THEN** agent（代理） MUST 展示候选 Node（节点运行时）checks（检查项）并等待用户选择
- **THEN** `check`（检查脚本）和 `verify`（验证脚本）候选 MUST 使用不同 check id（检查项标识）

#### Scenario: Python repository detection
- **WHEN** 目标仓库包含 Python（Python 语言）配置迹象
- **THEN** agent（代理） MUST 检查 `pyproject.toml`（项目配置）、`pytest.ini`（测试配置）、`tox.ini`（测试环境配置）、`noxfile.py`（任务配置）和 `requirements*.txt`（依赖清单）中的相关文件
- **THEN** agent（代理） MUST 优先建议 pytest（Python 测试运行器）和现有脚本作为候选 checks（检查项）
- **THEN** agent（代理） MUST 展示候选 Python（Python 语言）checks（检查项）并等待用户选择

#### Scenario: Mixed Node and Python repository
- **WHEN** 目标仓库同时包含 Node（节点运行时）和 Python（Python 语言）迹象
- **THEN** agent（代理） MUST 同时展示两类候选 checks（检查项）
- **THEN** agent（代理） MUST 让用户选择纳入哪些 checks（检查项）

#### Scenario: No recognized ecosystem fallback
- **WHEN** 目标仓库没有可识别的 Node（节点运行时）或 Python（Python 语言）迹象
- **THEN** agent（代理） MUST 继续使用固定 questionnaire（问答模板）
- **THEN** agent（代理） MUST 让用户手动提供 build（构建检查）和 verify（验证）候选命令
- **THEN** agent（代理） MUST 继续确认 `paths`（受影响路径）、`inputs`（缓存输入）、覆盖备份和 dry run（试运行）范围

#### Scenario: Draft config includes paths and inputs
- **WHEN** agent（代理）生成配置草案
- **THEN** 草案 MUST 同时支持 `build.checks`（构建检查项）和 `verify.checks`（验证检查项）
- **THEN** check id（检查项标识） MUST 使用短横线格式，例如 `build.node` 或 `verify.python-tests`
- **THEN** command（命令）默认 MUST 使用字符串形式
- **THEN** agent（代理） MUST 只在用户明确要求更稳定参数边界时使用列表形式 command（命令）
- **THEN** agent（代理） MUST 为 verify checks（验证检查项）建议 `paths`（受影响路径）
- **THEN** agent（代理） MUST 为 checks（检查项）建议 `inputs`（缓存输入）
- **THEN** agent（代理） MUST 在写入前展示 `paths`（受影响路径）和 `inputs`（缓存输入）并等待用户确认

#### Scenario: Draft config explains runtime tuning
- **WHEN** 配置草案包含 `verify.maxParallel`（最大并行检查数）、`verify.timeoutSeconds`（超时秒数）或 `parallel: true`（并行检查）
- **THEN** agent（代理） MUST 逐项解释这些运行参数
- **THEN** agent（代理） MUST 等待用户确认后才能写入这些运行参数
- **THEN** agent（代理） MUST NOT 为没有 `auto`（自动）语义的工具硬编码 `auto`（自动）参数

### Requirement: Guided initialization protects existing configuration
`build-and-verify-init` Skill（构建与验证初始化技能） MUST 在覆盖已有配置前保护用户已有 `.build-and-verify/config.json`（配置文件）。

#### Scenario: Existing config requires explicit overwrite confirmation
- **WHEN** 目标仓库已经存在 `.build-and-verify/config.json`（配置文件）
- **THEN** agent（代理） MUST 展示覆盖摘要
- **THEN** agent（代理） MUST 等待用户明确确认覆盖
- **THEN** agent（代理） MUST NOT 因用户沉默而覆盖已有配置

#### Scenario: Existing config is backed up before overwrite
- **WHEN** 用户确认覆盖已有 `.build-and-verify/config.json`（配置文件）
- **THEN** agent（代理） MUST 先复制旧配置到 `.build-and-verify/backups/config-YYYYMMDD-HHMMSS.json`（备份配置文件）
- **THEN** agent（代理） MUST 确保 `.build-and-verify/.gitignore`（忽略规则）包含 `/backups/`
- **THEN** agent（代理） MUST 在写入结果中报告备份路径

### Requirement: Guided initialization validates config and environment before completion
`build-and-verify-init` Skill（构建与验证初始化技能） MUST 在最终写入确认前执行定向依赖检查，并在写入后执行配置校验和用户选择范围的 dry run（试运行）。

#### Scenario: Config structure is validated after write
- **WHEN** agent（代理）写入 `.build-and-verify/config.json`（配置文件）
- **THEN** agent（代理） MUST 校验配置结构符合 build-and-verify（构建与验证）runner（运行器）契约
- **THEN** agent（代理） MUST 报告配置校验结果

#### Scenario: Targeted dependency checks report issues before write without blocking write
- **WHEN** 配置草案包含可识别依赖特征
- **THEN** agent（代理） MUST 在最终写入确认前执行 targeted dependency checks（定向依赖检查）
- **THEN** 命令包含 `pytest -n` 或 `--numprocesses` 时，agent（代理） MUST 检查 `pytest-xdist`（Pytest 并行插件）是否可用
- **THEN** 命令调用外部可执行文件时，agent（代理） MUST 检查该入口是否可找到
- **THEN** `paths`（受影响路径）或 `inputs`（缓存输入）指向不存在文件或目录时，agent（代理） MUST 提示用户确认
- **THEN** agent（代理） MUST 允许用户在存在依赖或环境问题时仍写入配置
- **THEN** agent（代理） MUST 明确列出问题、影响和建议
- **THEN** agent（代理） MUST NOT 未经用户授权就安装依赖或修改外部环境

#### Scenario: Dry run scope is selected by user
- **WHEN** agent（代理）准备执行 dry run（试运行）
- **THEN** agent（代理） MUST 展示可选试运行范围
- **THEN** dry run（试运行） MUST 只使用现有 `build`（构建检查）、默认 `verify`（快速验证）和显式 `verify --full`（完整验证）命令范围
- **THEN** 用户 MUST 明确选择要试运行的命令范围
- **THEN** agent（代理） MUST NOT 把只做 config（配置）结构校验当作完成初始化的 dry run（试运行）选择
- **THEN** agent（代理） MUST NOT 声称可以单独运行某个 check（检查项），除非 build-and-verify（构建与验证）runner（运行器）未来提供该能力
- **THEN** agent（代理） MUST NOT 默认运行 `verify --full`（完整验证）
- **THEN** 用户选择完整验证时，agent（代理） MUST 先说明成本和原因
```

Full source files remain canonical. If a required heading or scenario is missing here, regenerate the handoff or read the source spec directly. Supporting files (proposal, design, tasks) are referenced by hash only.
