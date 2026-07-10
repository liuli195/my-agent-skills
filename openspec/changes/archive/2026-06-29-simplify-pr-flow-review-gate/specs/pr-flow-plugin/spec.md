## ADDED Requirements

### Requirement: PR Flow init derives review gate mode from branch protection choice
系统 MUST 由 `pr-flow-init`（初始化）branch protection（分支保护）选择派生 review gate（审查门禁）模式，不新增单独 review gate mode（审查门禁模式）问题。

#### Scenario: Protected branches derive GitHub review gate
- **WHEN** 用户在 branch protection（分支保护）步骤选择一个或多个 protected branch（受保护分支）
- **THEN** init（初始化）草案 MUST 写入 `defaults.reviewGate.mode: github`
- **THEN** init（初始化）草案 MUST NOT require local review evidence（本地审查证据）

#### Scenario: No protected branches derive skipped review gate
- **WHEN** 用户在 branch protection（分支保护）步骤选择暂不配置远端保护
- **THEN** init（初始化）草案 MUST 写入 `defaults.reviewGate.mode: skip`
- **THEN** init（初始化）草案 MUST NOT keep or infer `defaults.reviewGate.mode: github`

## MODIFIED Requirements

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

### Requirement: PR Flow preserves build-and-verify verification mode boundaries
PR Flow（拉取请求流程）MUST preserve the boundary between default fast verify（快速验证） and explicit full verify（完整验证） when it references build-and-verify（构建与验证） commands.

#### Scenario: Complete path does not force full verification
- **WHEN** 用户运行 PR Flow complete（拉取请求流程收尾）
- **THEN** PR Flow（拉取请求流程） MUST NOT invoke `build-and-verify verify --full` unless the full command is supplied by an external PR CI（拉取请求持续集成）check
- **THEN** review gate（审查门禁） mode（模式） MUST NOT be treated as a request to run full verify（完整验证）

#### Scenario: Hotfix direct push uses explicit full verification command
- **WHEN** 用户运行 PR Flow hotfix（拉取请求流程热修复）
- **THEN** PR Flow（拉取请求流程） MAY run the configured `hotfix.verifyCommand`
- **THEN** 本仓库 `hotfix.verifyCommand` MAY be `python plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py verify --project . --full`
- **THEN** 该 full verify（完整验证） usage（使用） MUST remain explicit in `.pr-flow/config.yaml`

#### Scenario: Tweak path does not force full verification
- **WHEN** 用户运行 PR Flow tweak（拉取请求流程小改）
- **THEN** PR Flow（拉取请求流程） MUST NOT invoke `build-and-verify verify --full`
- **THEN** tweak（小改） path（路径） MUST continue to skip review gate（审查门禁） without upgrading verification mode（验证模式）

#### Scenario: Unknown verification mode is not inferred
- **WHEN** PR Flow（拉取请求流程） consumes review gate（审查门禁） mode（模式） or check status（检查状态）
- **THEN** PR Flow（拉取请求流程） MUST NOT infer that full verify（完整验证） has run unless an external check explicitly identifies the full command
- **THEN** PR Flow（拉取请求流程） MUST keep fast verify（快速验证） and full verify（完整验证） results（结果） distinct

## REMOVED Requirements

### Requirement: Cross-agent-review evidence generation
**Reason**: PR Flow（拉取请求流程）不再支持 local（本地）或 dual（双重）review gate（审查门禁），因此不再需要由 `cross-agent-review`（跨代理审查）生成 PR Flow 本地 evidence（证据）。
**Migration**: 需要审查门禁的仓库使用 `reviewGate.mode: github`；只依赖 checks（检查）的仓库使用 `reviewGate.mode: skip`。
