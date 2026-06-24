## RENAMED Requirements

FROM: Test framework plugin package supports Claude and Codex
TO: Build and Verify plugin package supports Claude and Codex

FROM: Test framework initializes standard artifacts
TO: Build and Verify initializes standard artifacts

FROM: Test framework provides unified configuration and commands
TO: Build and Verify provides unified configuration and commands

FROM: Test framework provides fast cache verification
TO: Build and Verify provides fast cache verification

## MODIFIED Requirements

### Requirement: Build and Verify plugin package supports Claude and Codex
系统 MUST 提供轻量 `build-and-verify`（构建与验证）Plugin（插件），同一套能力 MUST 同时面向 Claude（Claude 版本）和 Codex（Codex 版本）。

#### Scenario: Codex plugin structure
- **WHEN** 发布 `build-and-verify`（构建与验证）Plugin（插件）
- **THEN** 插件包 MUST 包含 `.codex-plugin/plugin.json`
- **THEN** Codex manifest（清单） MUST 声明插件 `name` 为 `build-and-verify`
- **THEN** Codex manifest（清单） MUST 声明 `version`、`description` 和 `skills`

#### Scenario: Claude plugin structure
- **WHEN** 发布 `build-and-verify`（构建与验证）Plugin（插件）
- **THEN** 插件包 MUST 包含 `.claude-plugin/plugin.json`
- **THEN** Claude manifest（清单） MUST 声明插件 `name` 为 `build-and-verify`
- **THEN** Claude manifest（清单） MUST 声明 `version`、`description` 和 `skills`

#### Scenario: Single skill surface
- **WHEN** 安装 `build-and-verify`（构建与验证）Plugin（插件）
- **THEN** 插件包 MUST 提供一个 `build-and-verify`（构建与验证）Skill（技能）
- **THEN** Skill（技能） MUST 调用共享确定性脚本，而不是复制多套流程逻辑

### Requirement: Build and Verify initializes standard artifacts
系统 MUST 为目标仓库初始化最小构建与验证产物结构。

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
- **WHEN** 目标仓库配置构建与验证
- **THEN** `.build-and-verify/config.json` MUST 支持 `build.checks`
- **THEN** `.build-and-verify/config.json` MUST 支持 `verify.checks`
- **THEN** `.build-and-verify/config.json` MUST NOT 要求独立的 `verify.fast.checks`

#### Scenario: Command entrypoint exposes minimum commands
- **WHEN** 目标仓库完成初始化
- **THEN** `python <build-and-verify-script> build --project <repo>` MUST 运行 configured `build.checks`
- **THEN** `python <build-and-verify-script> verify --project <repo>` MUST 运行默认 fast（快速验证）执行模式
- **THEN** `python <build-and-verify-script> verify --project <repo> --full` MUST 运行完整 `verify.checks`
- **THEN** `<build-and-verify-script>` MUST 是当前安装的 build-and-verify（构建与验证）Skill（技能）脚本路径，支持 project-level（项目级）安装路径和 user-level（用户级）安装路径

#### Scenario: Skill description owns command routing
- **WHEN** agent（代理）需要运行 build（构建检查）或 verify（验证）命令
- **THEN** agent（代理） MUST 使用 `build-and-verify`（构建与验证）Skill（技能）入口
- **THEN** agent（代理） MUST NOT 通过根目录 wrapper（包装入口）或旧 `test-framework`（测试框架）入口运行同等命令

#### Scenario: Full verify refreshes passed cache
- **WHEN** 用户运行 `python <build-and-verify-script> verify --project <repo> --full`
- **THEN** 系统 MUST NOT 通过读取 cache（缓存）跳过 configured `verify.checks`
- **THEN** 成功通过的 check（检查项） MUST 使用同一套 cache key（缓存键）写入或刷新 passed-result cache（通过结果缓存）
- **THEN** failed（失败）结果 MUST NOT 写入 passed-result cache（通过结果缓存）

### Requirement: Build and Verify provides fast cache verification
系统 MUST 将 fast（快速验证）实现为 full（完整验证）标准检查项上的 changed-files（变更文件）筛选和 passed-result cache（通过结果缓存）。

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
- **THEN** 系统 MUST NOT 因 cache miss（缓存未命中）自动运行 full（完整验证）

## MODIFIED Requirements

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
