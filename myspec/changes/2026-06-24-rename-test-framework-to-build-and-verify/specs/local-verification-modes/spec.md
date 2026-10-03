## MODIFIED Requirements

### Requirement: Initialized repositories expose standard verification modes
由 build-and-verify（构建与验证）Plugin（插件）初始化的仓库 MUST 通过同一套 configured checks（配置检查项）提供默认 fast（快速验证）和显式 full（完整验证）。

#### Scenario: Default verify applies fast cache execution
- **WHEN** 开发者运行 `python <build-and-verify-script> verify --project <repo>`
- **THEN** 系统 MUST 从 configured `verify.checks`（配置验证检查项）选择受 changed files（变更文件）影响的 checks（检查项）
- **THEN** 系统 MUST 对选中的 checks（检查项）应用 passed-result cache（通过结果缓存）
- **THEN** 系统 MUST NOT 跳过 changed-files（变更文件）筛选和 passed-result cache（通过结果缓存）而无条件运行所有 configured `verify.checks`

#### Scenario: Full verify requires explicit flag
- **WHEN** 开发者运行 `python <build-and-verify-script> verify --project <repo> --full`
- **THEN** 系统 MUST 运行所有 configured `verify.checks`
- **THEN** 系统 MUST NOT 使用 changed-files（变更文件）筛选跳过 checks（检查项）
- **THEN** 系统 MUST NOT 读取 cache（缓存）来跳过 checks（检查项）
- **THEN** 成功通过的 checks（检查项） MUST 写入或刷新 passed-result cache（通过结果缓存）
- **THEN** failed（失败）checks（检查项） MUST NOT 写入 passed-result cache（通过结果缓存）

#### Scenario: Target repository does not define separate fast checks
- **WHEN** 目标仓库声明 `.build-and-verify/config.json`
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
- **THEN** 系统 MUST NOT 自动运行 full（完整验证）路径

## ADDED Requirements

### Requirement: Full verification is restricted to explicit high-cost contexts
本仓库自动流程 MUST 默认使用 fast verify（快速验证），并将 full verify（完整验证）限制在明确允许的高成本上下文。

#### Scenario: Comet uses fast verification by default
- **WHEN** Comet（双星流程）读取本仓库默认 verify command（验证命令）
- **THEN** 该命令 MUST 调用 `build-and-verify`（构建与验证）入口
- **THEN** 该命令 MUST NOT 包含 `--full`

#### Scenario: Hotfix direct push may use full verification
- **WHEN** PR Flow（拉取请求流程）hotfix（热修复）直推路径读取 `hotfix.verifyCommand`
- **THEN** 该命令 MAY 调用 `build-and-verify verify --full`（构建与验证完整验证）
- **THEN** 该命令 MUST 作为配置中的显式命令存在

#### Scenario: PR CI may use full verification
- **WHEN** 本仓库未来新增 PR CI（拉取请求持续集成）工作流
- **THEN** 该工作流 MAY 调用 `build-and-verify verify --full`（构建与验证完整验证）
- **THEN** 该工作流 MUST 是面向 PR（拉取请求）的持续集成入口，而不是本地默认验证入口

#### Scenario: Other full verification requires confirmation
- **WHEN** agent（代理）在其他上下文准备运行 `build-and-verify verify --full`（构建与验证完整验证）
- **THEN** agent（代理） MUST 输出升级到 full verify（完整验证）的具体原因
- **THEN** agent（代理） MUST 等待用户确认后才能运行
