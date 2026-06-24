# local-verification-modes Specification

## Purpose
TBD - created by archiving change split-fast-full-verification. Update Purpose after archive.
## Requirements
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

