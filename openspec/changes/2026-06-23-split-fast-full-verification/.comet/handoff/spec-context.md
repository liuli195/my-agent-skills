# Comet Spec Context

- Change: split-fast-full-verification
- Phase: design
- Mode: beta
- Context hash: 3610ebb69513edb02dd335563207e94b770230b7b4d4a7da0ee41b21d42a29f2

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This beta context pack verbatim-projects spec files and references supporting artifacts by hash, not an agent-authored summary.

## Source References

- Source: openspec/changes/split-fast-full-verification/proposal.md
- SHA256: 17eaae994d8805675cbae3ca2d317d4955e3c84385da2498fa04ac01f9af0d40
- Source: openspec/changes/split-fast-full-verification/design.md
- SHA256: e8fea13ae3098d930df4302fce1d0f7a3091b33af35e8473881f091b4124d811
- Source: openspec/changes/split-fast-full-verification/tasks.md
- SHA256: af922cabcbddcfb355bc208d2c1b5432af534c1308d1e03d3a973cb638b9dc23
- Source: openspec/changes/split-fast-full-verification/specs/local-plugin-build-checks/spec.md
- SHA256: a976c36076ee8aa2fd9302442385a9368f895b72854dfe96212002cc15fedb65
- Source: openspec/changes/split-fast-full-verification/specs/local-verification-modes/spec.md
- SHA256: de474281f9a3b43243f0e6df159ff79f4ad71c983f59f35815cf177a25894e84
- Source: openspec/changes/split-fast-full-verification/specs/pr-flow-plugin/spec.md
- SHA256: 2499822caa636472c00b335c7cbb520e24429b8d9b599d310666915ae803f62d
- Source: openspec/changes/split-fast-full-verification/specs/test-framework-plugin/spec.md
- SHA256: ecbfdb8e5b56b60e9208b86e49baf77cc6a817a4331081f33798f978a7a52895

## Acceptance Projection

## openspec/changes/split-fast-full-verification/specs/local-plugin-build-checks/spec.md

- Source: openspec/changes/split-fast-full-verification/specs/local-plugin-build-checks/spec.md
- Lines: 1-20
- SHA256: a976c36076ee8aa2fd9302442385a9368f895b72854dfe96212002cc15fedb65

```md
## MODIFIED Requirements

### Requirement: Verify command follows initialized test framework contract
The repository SHALL（必须）provide a verify command generated or maintained by the test-framework Plugin（测试框架插件） contract.

#### Scenario: Verify command defaults to framework fast mode
- **WHEN** a developer runs `python plugins/test-framework/skills/test-framework/scripts/test_framework.py verify --project .`
- **THEN** the command uses `.test-framework/config.json` `verify.checks`
- **THEN** the command applies changed-files（变更文件） selection and passed-result cache（通过结果缓存）
- **THEN** the command does not bypass changed-files（变更文件） selection and passed-result cache（通过结果缓存） by unconditionally running every configured verify check

#### Scenario: Verify full mode runs all configured checks
- **WHEN** a developer runs `python plugins/test-framework/skills/test-framework/scripts/test_framework.py verify --project . --full`
- **THEN** the command runs all `.test-framework/config.json` `verify.checks`
- **THEN** the command does not use cache（缓存） hits to skip checks（检查项）
- **THEN** passed checks（已通过检查项） refresh passed-result cache（通过结果缓存）
- **THEN** failed checks（失败检查项） are not stored as passed-result cache（通过结果缓存）
- **THEN** the command does not rely on the default verify mode being full（全量验证）

#### Scenario: Comet config keeps guard-compatible command shim
- **WHEN** Comet（双星流程）reads root `.comet.yaml`
- **THEN** it defines `build_command: python plugins/test-framework/skills/test-framework/scripts/test_framework.py build --project .`
- **THEN** it defines `verify_command: python plugins/test-framework/skills/test-framework/scripts/test_framework.py verify --project .`
- **THEN** those commands act as the guard（守卫） compatibility shim（兼容层） for the test-framework runner（测试框架运行器）
```

## openspec/changes/split-fast-full-verification/specs/local-verification-modes/spec.md

- Source: openspec/changes/split-fast-full-verification/specs/local-verification-modes/spec.md
- Lines: 1-29
- SHA256: de474281f9a3b43243f0e6df159ff79f4ad71c983f59f35815cf177a25894e84

```md
## ADDED Requirements

### Requirement: Initialized repositories expose standard verification modes
由 test-framework Plugin（测试框架插件）初始化的仓库 MUST 通过同一套 configured checks（配置检查项）提供默认 fast（快速验证）和显式 full（全量验证）。

#### Scenario: Default verify applies fast cache execution
- **WHEN** 开发者运行 `python <test-framework-script> verify --project <repo>`
- **THEN** 系统 MUST 从 configured `verify.checks`（配置验证检查项）选择受 changed files（变更文件）影响的 checks（检查项）
- **THEN** 系统 MUST 对选中的 checks（检查项）应用 passed-result cache（通过结果缓存）
- **THEN** 系统 MUST NOT 跳过 changed-files（变更文件）筛选和 passed-result cache（通过结果缓存）而无条件运行所有 configured `verify.checks`

#### Scenario: Full verify requires explicit flag
- **WHEN** 开发者运行 `python <test-framework-script> verify --project <repo> --full`
- **THEN** 系统 MUST 运行所有 configured `verify.checks`
- **THEN** 系统 MUST NOT 使用 changed-files（变更文件）筛选跳过 checks（检查项）
- **THEN** 系统 MUST NOT 读取 cache（缓存）来跳过 checks（检查项）
- **THEN** 成功通过的 checks（检查项） MUST 写入或刷新 passed-result cache（通过结果缓存）
- **THEN** failed（失败）checks（检查项） MUST NOT 写入 passed-result cache（通过结果缓存）

#### Scenario: Target repository does not define separate fast checks
- **WHEN** 目标仓库声明 `.test-framework/config.json`
- **THEN** 配置 MUST 使用一套 `verify.checks`
- **THEN** 配置 MUST NOT 要求仓库维护独立的 `verify.fast.checks`
- **THEN** fast（快速验证） MUST 是框架执行模式，而不是仓库测试清单

#### Scenario: Fast verify caches only passed selected checks
- **WHEN** 默认 verify（验证）运行选中的 checks（检查项）
- **THEN** 系统 MUST 只复用输入、命令、配置和运行器版本均匹配的 passed（已通过）结果
- **THEN** 系统 MUST NOT 存储 failed（失败）检查结果作为通过缓存

#### Scenario: Fast verify does not automatically run full when no check is selected
- **WHEN** 默认 verify（验证）没有选中可运行 checks（检查项）
- **THEN** 系统 MUST 输出 checked（已检查）为空或等价信息
- **THEN** 系统 MUST 输出 full-not-run（全量未运行）为 true 或等价信息
- **THEN** 系统 MUST NOT 自动运行 full（全量验证）路径
```

## openspec/changes/split-fast-full-verification/specs/pr-flow-plugin/spec.md

- Source: openspec/changes/split-fast-full-verification/specs/pr-flow-plugin/spec.md
- Lines: 1-56
- SHA256: 2499822caa636472c00b335c7cbb520e24429b8d9b599d310666915ae803f62d

```md
## MODIFIED Requirements

### Requirement: Repository PR Flow configuration
系统 MUST 使用 `.pr-flow/config.yaml` 保存仓库共享 PR Flow（拉取请求流程）配置，并将该文件纳入 Git（版本管理）。

#### Scenario: Init creates local configuration
- **WHEN** 用户运行 repo init（仓库初始化）
- **THEN** 系统 MUST 创建 `.pr-flow/config.yaml`
- **THEN** 系统 MUST 创建 PR body template（拉取请求正文模板）
- **THEN** 系统 MUST 创建 `.pr-flow/.gitignore`，忽略本地运行记录和最后状态

#### Scenario: Init does not write GitHub settings
- **WHEN** 用户运行 repo init
- **THEN** 系统 MUST 输出 GitHub Rulesets（GitHub 规则集）建议配置
- **THEN** 系统 MUST NOT 调用 `gh api` 或其他 GitHub API（接口）写入远端仓库设置
- **THEN** 系统 MUST NOT 声称已回读验证 GitHub Rulesets

#### Scenario: Defaults and branch overrides
- **WHEN** `.pr-flow/config.yaml` 声明配置
- **THEN** 配置 MUST 支持 `defaults` 默认规则
- **THEN** 配置 MUST 支持 `branches` 分支覆盖
- **THEN** 分支覆盖 MUST 只覆盖该目标分支需要改变的字段

#### Scenario: Hotfix defaults use explicit full verification
- **WHEN** repo init（仓库初始化）生成默认 `hotfix.verifyCommand`
- **THEN** 该命令 MUST 使用仓库显式 full（完整）验证入口
- **THEN** 该命令 MUST NOT 依赖默认 verify（验证）模式等同于 full（完整）验证

### Requirement: Hotfix direct push path
系统 MUST 提供 hotfix（热修复）路径，用于紧急直推显式允许的目标分支。

#### Scenario: Hotfix allowed branch
- **WHEN** 用户运行 hotfix
- **THEN** 目标分支 MUST 在配置中显式 `allowHotfixPush: true`
- **THEN** 用户 MUST 显式指定目标分支

#### Scenario: Hotfix base matches target
- **WHEN** 用户运行 hotfix
- **THEN** 系统 MUST fetch（拉取）目标远端分支
- **THEN** 当前提交 MUST 基于目标分支最新 head commit（头提交）
- **THEN** 系统 MUST 拒绝旧 base（基线）或错误 base 的 hotfix

#### Scenario: Hotfix verification and confirmation
- **WHEN** 用户运行 hotfix
- **THEN** 系统 MUST 先确认 authorization phrase（授权短语）配置存在且算法受支持
- **THEN** 系统 MUST 运行 `hotfix.verifyCommand`
- **THEN** `hotfix.verifyCommand` MUST 指向显式 full（全量验证）入口
- **THEN** `hotfix.verifyCommand` MUST NOT 依赖默认 verify（验证）模式等同于 full（全量验证）
- **THEN** 验证通过后系统 MUST 校验 authorization phrase
- **THEN** 确认通过后系统 MAY push（推送）到受保护分支

#### Scenario: Hotfix remote verification
- **WHEN** hotfix push（热修复推送）完成
- **THEN** 系统 MUST 回读远端目标分支
- **THEN** 远端目标分支 MUST 等于预期 head commit（头提交）
- **THEN** 系统 MUST 写入最小本地审计记录
```

## openspec/changes/split-fast-full-verification/specs/test-framework-plugin/spec.md

- Source: openspec/changes/split-fast-full-verification/specs/test-framework-plugin/spec.md
- Lines: 1-70
- SHA256: ecbfdb8e5b56b60e9208b86e49baf77cc6a817a4331081f33798f978a7a52895

```md
## ADDED Requirements

### Requirement: Test framework plugin package supports Claude and Codex
系统 MUST 提供轻量 `test-framework` Plugin（测试框架插件），同一套能力 MUST 同时面向 Claude（Claude 版本）和 Codex（Codex 版本）。

#### Scenario: Codex plugin structure
- **WHEN** 发布 `test-framework` Plugin（插件）
- **THEN** 插件包 MUST 包含 `.codex-plugin/plugin.json`
- **THEN** Codex manifest（清单） MUST 声明插件 `name`、`version`、`description` 和 `skills`

#### Scenario: Claude plugin structure
- **WHEN** 发布 `test-framework` Plugin（插件）
- **THEN** 插件包 MUST 包含 `.claude-plugin/plugin.json`
- **THEN** Claude manifest（清单） MUST 声明插件 `name`、`version`、`description` 和 `skills`

#### Scenario: Single skill surface
- **WHEN** 安装 `test-framework` Plugin（插件）
- **THEN** 插件包 MUST 提供一个 `test-framework` Skill（技能）
- **THEN** Skill（技能） MUST 调用共享确定性脚本，而不是复制多套流程逻辑

### Requirement: Test framework initializes standard artifacts
系统 MUST 为目标仓库初始化最小测试框架产物结构。

#### Scenario: Init creates standard files
- **WHEN** 用户对目标仓库运行 test-framework init（测试框架初始化）
- **THEN** 系统 MUST 创建 `.test-framework/config.json`
- **THEN** 系统 MUST 创建 `.test-framework/.gitignore`
- **THEN** 系统 MUST NOT 向目标仓库复制 runner（运行器）脚本

#### Scenario: Init defines local cache location
- **WHEN** 初始化产物写入目标仓库
- **THEN** 系统 MUST 使用 `.test-framework/cache/` 作为本地 cache（缓存）目录
- **THEN** 系统 MUST 创建 `.test-framework/cache/` 目录
- **THEN** 系统 MUST NOT 要求将 cache（缓存）内容纳入 Git（版本管理）

#### Scenario: Init refuses conflicting files
- **WHEN** 目标仓库已经存在 `.test-framework/config.json` 或 `.test-framework/.gitignore`
- **THEN** 系统 MUST 在写入任何初始化产物前拒绝静默覆盖
- **THEN** 系统 MUST 返回 non-zero（非零）退出码并报告 target-repository-relative（目标仓库相对）冲突路径

#### Scenario: Init stays uncoupled from repository business logic
- **WHEN** 插件初始化目标仓库
- **THEN** 模板 MUST NOT 内置 PR Flow（拉取请求流程）、Release Flow（发布流程）、Comet（双星流程）或任一具体仓库业务检查
- **THEN** 仓库业务检查 MUST 只通过 `.test-framework/config.json` 声明

### Requirement: Test framework provides unified configuration and commands
系统 MUST 通过一个配置文件和一个命令入口表达 build（构建检查）与 verify（验证）行为。

#### Scenario: Config declares canonical checks
- **WHEN** 目标仓库配置测试框架
- **THEN** `.test-framework/config.json` MUST 支持 `build.checks`
- **THEN** `.test-framework/config.json` MUST 支持 `verify.checks`
- **THEN** `.test-framework/config.json` MUST NOT 要求独立的 `verify.fast.checks`

#### Scenario: Command entrypoint exposes minimum commands
- **WHEN** 目标仓库完成初始化
- **THEN** `python <test-framework-script> build --project <repo>` MUST 运行 configured `build.checks`
- **THEN** `python <test-framework-script> verify --project <repo>` MUST 运行默认 fast（快速验证）执行模式
- **THEN** `python <test-framework-script> verify --project <repo> --full` MUST 运行完整 `verify.checks`
- **THEN** `<test-framework-script>` MUST 是当前安装的 test-framework Skill（技能）脚本路径，支持 project-level（项目级）安装路径和 user-level（用户级）安装路径

#### Scenario: Full verify refreshes passed cache
- **WHEN** 用户运行 `python <test-framework-script> verify --project <repo> --full`
- **THEN** 系统 MUST NOT 通过读取 cache（缓存）跳过 configured `verify.checks`
- **THEN** 成功通过的 check（检查项） MUST 使用同一套 cache key（缓存键）写入或刷新 passed-result cache（通过结果缓存）
- **THEN** failed（失败）结果 MUST NOT 写入 passed-result cache（通过结果缓存）

### Requirement: Test framework provides fast cache verification
系统 MUST 将 fast（快速验证）实现为 full（全量验证）标准检查项上的 changed-files（变更文件）筛选和 passed-result cache（通过结果缓存）。

#### Scenario: Fast verify selects configured checks by changed files
- **WHEN** 用户运行 `python <test-framework-script> verify --project <repo>`
- **THEN** 系统 MUST 默认从 worktree（工作区）收集 changed files（变更文件）
- **THEN** 默认 worktree（工作区）来源 MUST 包含 staged tracked changes（已暂存已跟踪变更）、unstaged tracked changes（未暂存已跟踪变更）和 untracked non-ignored files（未跟踪且未忽略文件）
- **THEN** 系统 MUST 根据 configured check（配置检查项）的 `paths` 选择受影响 checks（检查项）

#### Scenario: Cache uses passed results only
- **WHEN** 选中的 check（检查项）存在匹配 cache key（缓存键）
- **THEN** 系统 MUST 只复用 passed（已通过）的缓存结果
- **THEN** cache key（缓存键） MUST 覆盖 check id（检查项标识）、command（命令）、inputs（输入）、config（配置）、Python（运行器）版本、framework（框架）版本和 cache（缓存）版本
- **THEN** directory hashing（目录哈希） MUST 排除 `.test-framework/cache/`、`.git/` 和运行态缓存目录
- **THEN** 系统 MUST NOT 缓存 failed（失败）结果作为通过结果

#### Scenario: Cache miss runs selected check only
- **WHEN** 选中的 check（检查项）没有可用 passed-result cache（通过结果缓存）
- **THEN** 系统 MUST 运行该 check（检查项）自身
- **THEN** 系统 MUST NOT 因 cache miss（缓存未命中）自动运行 full（全量验证）
```

Full source files remain canonical. If a required heading or scenario is missing here, regenerate the handoff or read the source spec directly. Supporting files (proposal, design, tasks) are referenced by hash only.
