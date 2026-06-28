# test-framework-plugin Specification

## Purpose
This capability keeps the OpenSpec（开放规格） id `test-framework-plugin` to model the rename（改名） of an existing capability. Its shipped Plugin（插件） and Skill（技能） name is `build-and-verify`, which is the repository build（构建检查） and verify（验证） entry point.
## Requirements
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

### Requirement: Build and Verify initializes standard artifacts
系统 MUST 为目标仓库初始化最小构建检查和验证产物结构。

#### Scenario: Init creates standard files
- **WHEN** 用户对目标仓库运行 build-and-verify init（构建与验证初始化）
- **THEN** 系统 MUST 创建 `.build-and-verify/config.json`
- **THEN** 系统 MUST 创建 `.build-and-verify/.gitignore`
- **THEN** 系统 MUST NOT 向目标仓库复制 runner（运行器）脚本

#### Scenario: Init defines local cache location
- **WHEN** 初始化产物写入目标仓库
- **THEN** 系统 MUST 使用 `.build-and-verify/cache/` 作为本地 cache（缓存）目录
- **THEN** 系统 MUST 创建 `.build-and-verify/cache/` 目录
- **THEN** 系统 MUST NOT 要求将 cache（缓存）内容纳入 Git（版本管理）

#### Scenario: Init refuses conflicting files
- **WHEN** 目标仓库已经存在 `.build-and-verify/config.json` 或 `.build-and-verify/.gitignore`
- **THEN** 系统 MUST 在写入任何初始化产物前拒绝静默覆盖
- **THEN** 系统 MUST 返回 non-zero（非零）退出码并报告 target-repository-relative（目标仓库相对）冲突路径

#### Scenario: Init stays uncoupled from repository business logic
- **WHEN** 插件初始化目标仓库
- **THEN** 模板 MUST NOT 内置 PR Flow（拉取请求流程）、Release Flow（发布流程）、Comet（双星流程）或任一具体仓库业务检查
- **THEN** 仓库业务检查 MUST 只通过 `.build-and-verify/config.json` 声明

### Requirement: Build and Verify provides unified configuration and commands
系统 MUST 通过一个配置文件和一个命令入口表达 build（构建检查）与 verify（验证）行为。

#### Scenario: Config declares canonical checks
- **WHEN** 目标仓库配置 build-and-verify（构建与验证）
- **THEN** `.build-and-verify/config.json` MUST 支持 `build.checks`
- **THEN** `.build-and-verify/config.json` MUST 支持 `verify.checks`
- **THEN** `.build-and-verify/config.json` MUST NOT 要求独立的 `verify.fast.checks`

#### Scenario: Command entrypoint exposes minimum commands
- **WHEN** 目标仓库完成初始化
- **THEN** `python <build-and-verify-script> build --project <repo>` MUST 运行 configured `build.checks`
- **THEN** `python <build-and-verify-script> verify --project <repo>` MUST 运行默认 fast（快速验证）执行模式
- **THEN** `python <build-and-verify-script> verify --project <repo> --full` MUST 运行完整 `verify.checks`
- **THEN** `<build-and-verify-script>` MUST 是当前安装的 build-and-verify Skill（技能）脚本路径，支持 project-level（项目级）安装路径和 user-level（用户级）安装路径

#### Scenario: Full verify refreshes passed cache
- **WHEN** 用户运行 `python <build-and-verify-script> verify --project <repo> --full`
- **THEN** 系统 MUST NOT 通过读取 cache（缓存）跳过 configured `verify.checks`
- **THEN** 成功通过的 check（检查项） MUST 使用同一套 cache key（缓存键）写入或刷新 passed-result cache（通过结果缓存）
- **THEN** failed（失败）结果 MUST NOT 写入 passed-result cache（通过结果缓存）

### Requirement: Build and Verify provides fast cache verification
系统 MUST 将 fast（快速验证）实现为 full（全量验证）标准检查项上的 changed-files（变更文件）筛选和 passed-result cache（通过结果缓存）。

#### Scenario: Fast verify selects configured checks by changed files
- **WHEN** 用户运行 `python <build-and-verify-script> verify --project <repo>`
- **THEN** 系统 MUST 默认从 worktree（工作区）收集 changed files（变更文件）
- **THEN** 默认 worktree（工作区）来源 MUST 包含 staged tracked changes（已暂存已跟踪变更）、unstaged tracked changes（未暂存已跟踪变更）和 untracked non-ignored files（未跟踪且未忽略文件）
- **THEN** 系统 MUST 根据 configured check（配置检查项）的 `paths` 选择受影响 checks（检查项）

#### Scenario: Fast verify treats pathless checks as global checks
- **WHEN** configured verify check（配置验证检查项）没有 `paths`
- **THEN** 系统 MUST 将该 check（检查项）视为 global check（全局检查项）
- **THEN** 默认 fast verify（快速验证） MUST 在存在任意 changed file（变更文件）时选择该 check（检查项）
- **THEN** 默认 fast verify（快速验证） MUST 在没有 changed files（变更文件）时不选择该 check（检查项）
- **THEN** 没有 `inputs` 的 global check（全局检查项） MUST 使用当前 changed files（变更文件）作为 cache key（缓存键）的输入来源

#### Scenario: Cache uses passed results only
- **WHEN** 选中的 check（检查项）存在匹配 cache key（缓存键）
- **THEN** 系统 MUST 只复用 passed（已通过）的缓存结果
- **THEN** cache key（缓存键） MUST 覆盖 check id（检查项标识）、command（命令）、inputs（输入）、config（配置）、Python（运行器）版本、framework（框架）版本和 cache（缓存）版本
- **THEN** directory hashing（目录哈希） MUST 排除 `.build-and-verify/cache/`、`.git/` 和运行态缓存目录
- **THEN** 系统 MUST NOT 缓存 failed（失败）结果作为通过结果

#### Scenario: Cache miss runs selected check only
- **WHEN** 选中的 check（检查项）没有可用 passed-result cache（通过结果缓存）
- **THEN** 系统 MUST 运行该 check（检查项）自身
- **THEN** 系统 MUST NOT 因 cache miss（缓存未命中）自动运行 full（全量验证）

### Requirement: Build and Verify has no root-level Python test configuration dependency
系统 MUST 不依赖根目录 Python（Python 语言）测试配置来定义本仓库 build（构建检查）或 verify（验证）行为。

#### Scenario: Root pyproject test config is absent
- **WHEN** 本仓库 build-and-verify（构建与验证）配置完成迁移
- **THEN** 根目录 `pyproject.toml` MUST NOT 存在
- **THEN** `.build-and-verify/config.json` 中的 pytest（Python 测试运行器）命令 MUST 显式声明测试路径和所需命令参数

#### Scenario: No root wrapper entrypoint
- **WHEN** 本仓库活跃自动化和 guard（守卫）命令文件被检查
- **THEN** 它们 MUST NOT 引用根目录测试 wrapper（包装入口）
- **THEN** 它们 MUST 引用 `plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py` 或当前安装的 build-and-verify（构建与验证）Skill（技能）脚本

### Requirement: Build and Verify provides template-driven guided initialization
系统 MUST 通过 `build-and-verify-init` Skill（构建与验证初始化技能）提供模板化对话式初始化向导，用于为通用仓库生成 `.build-and-verify/config.json`（配置文件）。

#### Scenario: Guided initialization uses fixed questionnaire
- **WHEN** agent（代理）使用 `build-and-verify-init` Skill（构建与验证初始化技能）
- **THEN** Skill（技能） MUST 指示 agent（代理）读取固定 questionnaire（问答模板）
- **THEN** questionnaire（问答模板） MUST 定义固定问题、固定选项、后果说明和跳转规则
- **THEN** questionnaire（问答模板） MUST 覆盖目标仓库路径确认、扫描授权、候选 check（检查项）确认、`paths`（受影响路径）确认、并行与超时确认、覆盖与最终写入确认
- **THEN** agent（代理） MUST 默认从 `paths`（受影响路径）和 command（命令）来源推导 `inputs`（缓存输入），并在最终写入确认摘要中展示
- **THEN** 覆盖已有配置时，agent（代理） MUST 使用默认备份路径，不得单独要求用户选择备份路径
- **THEN** agent（代理） MUST NOT 自由编造初始化问题或跳过最终写入确认

#### Scenario: Guided initialization uses progressive disclosure references
- **WHEN** 发布 `build-and-verify-init` Skill（构建与验证初始化技能）
- **THEN** Skill（技能） MUST 将固定问答模板放在独立 reference（参考文件）
- **THEN** Skill（技能） MUST 将已有配置、Node（节点运行时）、Python（Python 语言）和通用候选识别规则放在独立 reference（参考文件）
- **THEN** Skill（技能） MUST 将配置草案规则放在独立 reference（参考文件）
- **THEN** Skill（技能） MUST 将依赖检查、环境检查和配置校验规则放在独立 reference（参考文件）

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

#### Scenario: Generic candidate discovery
- **WHEN** 目标仓库包含 `Makefile`（任务文件）、`scripts/`（脚本目录）、`tests/`（测试目录）或 `openspec/`（开放规格目录）等通用信号
- **THEN** agent（代理） MUST 分类候选 checks（检查项），并展示 source（来源）、confidence（置信度）、reason（纳入理由）和 risk（风险提示）
- **THEN** agent（代理） MUST NOT 运行候选 command（命令）
- **THEN** 风险候选 MUST NOT 默认纳入配置草案

#### Scenario: Mixed repository
- **WHEN** 目标仓库同时包含 Node（节点运行时）、Python（Python 语言）或通用候选信号
- **THEN** agent（代理） MUST 同时展示多类候选 checks（检查项）
- **THEN** agent（代理） MUST 让用户选择纳入哪些 checks（检查项）

#### Scenario: No recognized ecosystem fallback
- **WHEN** 目标仓库没有可识别的已有配置、Node（节点运行时）、Python（Python 语言）或通用候选信号
- **THEN** agent（代理） MUST 继续使用固定 questionnaire（问答模板）
- **THEN** agent（代理） MUST 让用户手动提供 build（构建检查）和 verify（验证）候选命令
- **THEN** agent（代理） MUST 继续确认 `paths`（受影响路径）和运行参数，自动推导 `inputs`（缓存输入），并使用默认备份路径完成覆盖备份和配置校验

#### Scenario: Draft config includes paths and inputs
- **WHEN** agent（代理）生成配置草案
- **THEN** 草案 MUST 同时支持 `build.checks`（构建检查项）和 `verify.checks`（验证检查项）
- **THEN** check id（检查项标识） MUST 使用短横线格式，例如 `build.node` 或 `verify.python-tests`
- **THEN** command（命令）默认 MUST 使用字符串形式
- **THEN** agent（代理） MUST 只在用户明确要求更稳定参数边界时使用列表形式 command（命令）
- **THEN** agent（代理） MUST 为 verify checks（验证检查项）建议 `paths`（受影响路径）
- **THEN** agent（代理） MUST 从 `paths`（受影响路径）和 command（命令）来源推导 `inputs`（缓存输入）
- **THEN** agent（代理） MUST 在写入前等待用户确认 `paths`（受影响路径），并在最终写入摘要中展示自动推导的 `inputs`（缓存输入）

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
- **THEN** agent（代理） MUST 在 backups（备份）目录不存在时先创建该目录
- **THEN** agent（代理） MUST 先复制旧配置到 `.build-and-verify/backups/config-YYYYMMDD-HHMMSS.json`（备份配置文件）
- **THEN** agent（代理） MUST 确保 `.build-and-verify/.gitignore`（忽略规则）包含 `/backups/`
- **THEN** agent（代理） MUST NOT 要求用户单独选择备份路径
- **THEN** agent（代理） MUST 在写入结果中报告备份路径

### Requirement: Guided initialization validates config and environment before completion
`build-and-verify-init` Skill（构建与验证初始化技能） MUST 在最终写入确认前执行定向依赖检查和环境检查，并在写入后执行配置校验。

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

#### Scenario: Environment checks report issues before write without blocking write
- **WHEN** agent（代理）准备写入 `.build-and-verify/config.json`（配置文件）
- **THEN** agent（代理） MUST 在最终写入确认前执行 environment checks（环境检查）
- **THEN** agent（代理） MUST 检查目标仓库路径存在且是目录
- **THEN** agent（代理） MUST 检查配置目录可创建或可写入
- **THEN** 覆盖已有配置时，agent（代理） MUST 检查备份目录可创建且备份路径仍在目标仓库内
- **THEN** agent（代理） MUST 允许用户在存在依赖或环境问题时仍写入配置
- **THEN** agent（代理） MUST 明确说明用户可以让 agent（代理）协助处理环境和外部依赖问题
