# Comet Design Handoff

- Change: agent-guard-marketplace-subscription
- Phase: design
- Mode: compact
- Context hash: 2c8d7c07fcb15918708d33e7c2deb73a711224966f1344cd4c60c673190576d1

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/agent-guard-marketplace-subscription/proposal.md

- Source: openspec/changes/agent-guard-marketplace-subscription/proposal.md
- Lines: 1-36
- SHA256: 08b488548b2815a8a0b1286eb2653d5d383648a55cc15e662606d6f77974bf31

```md
## Why

Agent Guard Plugin（代理守卫插件）已经转向 Plugin-first（插件优先），但当前安装契约仍混杂了旧的 user-level Skill（用户级技能）同步、Claude Junction（Claude 目录联接）和非标准 marketplace（市场）文件。需要把发布与订阅面收敛到 Codex 和 Claude 可使用的插件包，并支持 personal marketplace（个人市场）与 repo marketplace（仓库市场）。

## What Changes

- **BREAKING**: 移除 user-level Skill installation（用户级技能安装）兼容路径，不再保留 `scripts/install/install_user_skill.ps1`、`scripts/install/sync_claude_junction.ps1` 和 `scripts/install/verify_install.py` 作为 Agent Guard 发布契约。
- **BREAKING**: 移除 Claude Junction（Claude 目录联接）作为 Claude 兼容方式；Claude 兼容改由插件包内 `.claude-plugin/plugin.json` 和同一插件内容验证。
- 将 Agent Guard Plugin 的安装/验证契约改为 marketplace subscription（市场订阅）优先，覆盖 Codex 与 Claude 两个目标。
- 正式订阅源指向 GitHub repo（GitHub 仓库）的 `marketplace` 发布分支，不使用 tag（标签）或 commit（提交）固定版本。
- 本仓库维护 Codex `.agents/plugins/marketplace.json` 和 Claude `.claude-plugin/marketplace.json` 两套 marketplace catalog（市场目录），共享同一个 `plugins/agent-guard` 插件包。
- 支持 personal marketplace（个人市场）和 repo marketplace（仓库市场）两类入口；默认不写用户目录，所有写入仍需要明确授权。
- 对 marketplace entry（市场条目）使用当前插件约定：`source` 对象、`policy.installation`、`policy.authentication` 和 `category`。
- 更新相关测试和 OpenSpec specs，使验证不再引用旧用户级 Skill 安装兼容层。

## Capabilities

### New Capabilities

### Modified Capabilities
- `agent-guard-plugin-runtime`: 插件安装/验证要求改为 marketplace subscription，并支持 personal/repo marketplace。
- `agent-guard-skill-entrypoints`: 删除 user-level Skill installation verification 作为发布契约，场景化 Skill 入口只由插件包发布。

## Impact

- `plugins/agent-guard/.codex-plugin/plugin.json`
- `plugins/agent-guard/.claude-plugin/plugin.json`
- `plugins/agent-guard/skills/agent-guard/scripts/install_agent_guard_plugin.py`
- `plugins/agent-guard/skills/agent-guard*/SKILL.md` 和相关 reference（参考文档）
- `scripts/install/` 下旧用户级 Skill 安装脚本
- `tests/test_agent_guard_plugin_installer.py`
- `tests/test_agent_guard_plugin_package.py`
- `tests/test_agent_guard_plugin_runtime_e2e.py`
- `tests/test_user_skill_install.py`
- `openspec/specs/agent-guard-plugin-runtime/spec.md`
- `openspec/specs/agent-guard-skill-entrypoints/spec.md`
```

## openspec/changes/agent-guard-marketplace-subscription/design.md

- Source: openspec/changes/agent-guard-marketplace-subscription/design.md
- Lines: 1-118
- SHA256: f269225893d5ea93930e40ca813a69fe829097fa61e94fdc088da1815c9f619d

[TRUNCATED]

```md
## Context

Agent Guard Plugin（代理守卫插件）当前已经采用 Plugin-first（插件优先）架构：runtime（运行时）、hook router（钩子路由器）、hooks（钩子）和 Skill（技能）入口都位于 `plugins/agent-guard/`。但发布路径仍不干净：

- 插件包已有 `.codex-plugin/plugin.json` 和 `.claude-plugin/plugin.json`。
- `install_agent_guard_plugin.py` 当前写入 `codex_home/plugins/agent-guard`、`claude_home/plugins/agent-guard`，并维护简单的 `marketplace.json`。
- `scripts/install/` 仍维护 user-level Skill（用户级技能）同步和 Claude Junction（目录联接）兼容层。
- `agent-guard-skill-entrypoints` spec 仍要求 user-level Skill installation verification（用户级技能安装验证）。

这些路径会让“插件订阅”和“技能复制”同时成为发布契约，导致 Codex 与 Claude 的安装面不一致。

## Goals / Non-Goals

**Goals:**

- 以 marketplace subscription（市场订阅）作为 Agent Guard 的唯一发布/订阅入口。
- 同一个 `plugins/agent-guard` 包同时提供 Codex 和 Claude 可验证 manifest（清单）。
- 支持 personal marketplace（个人市场）和 repo marketplace（仓库市场）。
- 保留 dry-run（试运行）默认行为，所有写入仍需显式授权。
- 更新 OpenSpec specs、安装器、测试和文档，删除旧 user-level Skill/Junction 契约。

**Non-Goals:**

- 不实际安装到当前用户的 Codex 或 Claude 目录。
- 不配置用户环境、不创建 Hook（钩子）、不初始化 Guard Profile（守卫画像）。
- 不新增 runtime（运行时）业务语义。
- 不保留旧 user-level Skill 安装脚本作为兼容层。

## Decisions

### 1. Marketplace 是唯一发布入口

Agent Guard 的订阅入口改为 marketplace entry（市场条目），不再把 `.agents/skills/*` 同步当作发布动作。

替代方案：

- 保留 user-level Skill 安装作为兼容层：迁移成本低，但继续制造两套入口。
- 只支持 Codex marketplace：实现小，但不满足 Claude 目标。
- 统一 marketplace 订阅：契约清楚，测试可直接覆盖个人/仓库两类入口。

选择统一 marketplace 订阅，因为它和 Plugin-first 基线一致。

### 2. GitHub 发布分支是正式订阅源

Agent Guard 的正式 marketplace subscription（市场订阅）指向 GitHub repo（GitHub 仓库）的 `marketplace` 发布分支，不使用 tag（标签）或 commit（提交）固定版本。

替代方案：

- 使用 tag 或 commit 固定版本：可复现性更强，但不符合本 change 的订阅更新策略。
- 使用主开发分支：操作简单，但发布纪律不清晰。
- 使用独立发布分支：订阅入口稳定，发布内容可以独立验证后推进。

选择 `marketplace` 发布分支，因为它贴近 Codex 和 Claude 的 GitHub marketplace 使用方式，同时避免把开发分支直接暴露给订阅者。

### 3. Codex 与 Claude 维护双 catalog，共享同一插件包

仓库内同时维护：

- Codex marketplace catalog（市场目录）：`.agents/plugins/marketplace.json`
- Claude marketplace catalog（市场目录）：`.claude-plugin/marketplace.json`

两套 catalog 都解析到同一个自包含插件包 `plugins/agent-guard`。插件包内部包含 `.codex-plugin/plugin.json`、`.claude-plugin/plugin.json`、skills、hooks、runtime、scripts 和 assets。Claude 安装会复制插件目录到 cache（缓存），所以插件包不能依赖目录外文件。

### 4. Codex 本地 marketplace entry 保持当前 schema（条目结构）

Codex personal/repo marketplace 使用当前 marketplace entry：

```json
{
  "name": "agent-guard",
  "source": {
    "source": "local",
    "path": "./plugins/agent-guard"
  },
  "policy": {
    "installation": "AVAILABLE",
    "authentication": "ON_INSTALL"
  },
  "category": "Productivity"
}
```

Full source: openspec/changes/agent-guard-marketplace-subscription/design.md

## openspec/changes/agent-guard-marketplace-subscription/tasks.md

- Source: openspec/changes/agent-guard-marketplace-subscription/tasks.md
- Lines: 1-26
- SHA256: 04aa9808173d23ba61a9950aaa9e44ba21b63bb924152a33bad1578b8170fcab

```md
## 1. Contract And Test Baseline

- [ ] 1.1 更新 `agent-guard-plugin-runtime` 和 `agent-guard-skill-entrypoints` specs，确认 marketplace subscription（市场订阅）是唯一发布入口。
- [ ] 1.2 调整 installer tests（安装器测试），覆盖 `target` 与 `scope` 分离、personal marketplace（个人市场）、repo marketplace（仓库市场）和 GitHub `marketplace` 发布分支。
- [ ] 1.3 调整 package tests（插件包测试），校验 `.codex-plugin`、`.claude-plugin`、hooks、runtime 和 Skill 入口，不再校验 user-level Skill installation（用户级技能安装）。
- [ ] 1.4 删除或替换旧 `test_user_skill_install.py`，确保测试不再引用 Claude Junction（Claude 目录联接）或 `.agents/skills/agent-guard` 安装兼容层。

## 2. Marketplace Installer

- [ ] 2.1 重构 `install_agent_guard_plugin.py`，把 `--target codex|claude|all` 和 `--scope personal|repo|all` 分开处理。
- [ ] 2.2 实现 personal marketplace（个人市场）和 repo marketplace（仓库市场）的 dry-run 输出、授权写入和验证。
- [ ] 2.3 生成并校验 Codex `.agents/plugins/marketplace.json` 与 Claude `.claude-plugin/marketplace.json`，两者共享 `plugins/agent-guard` 插件包。
- [ ] 2.4 生成并校验 Codex entry（条目）包含 `source`、`policy.installation`、`policy.authentication` 和 `category`。
- [ ] 2.5 保持安全声明：不初始化 Guard Profile（守卫画像）、不安装 project hooks（项目钩子）、不修改 git config（Git 配置）。

## 3. Remove Legacy Install Path

- [ ] 3.1 删除 `scripts/install/install_user_skill.ps1`、`scripts/install/sync_claude_junction.ps1` 和 `scripts/install/verify_install.py`。
- [ ] 3.2 更新 `scripts/install/README.md` 或删除旧 README，避免继续指向 user-level Skill installation（用户级技能安装）。
- [ ] 3.3 更新 Agent Guard Skill references（参考文档），把 Plugin update（插件更新）说明改为 marketplace subscription（市场订阅）流程。

## 4. Verification

- [ ] 4.1 运行 `openspec validate --all --strict --json`。
- [ ] 4.2 运行相关 pytest（测试）：plugin package、plugin installer、plugin runtime e2e 和被修改的 extraction tests。
- [ ] 4.3 定向扫描确认没有活跃文档或测试继续引用旧 user-level Skill installation（用户级技能安装）兼容层。
```

## openspec/changes/agent-guard-marketplace-subscription/specs/agent-guard-plugin-runtime/spec.md

- Source: openspec/changes/agent-guard-marketplace-subscription/specs/agent-guard-plugin-runtime/spec.md
- Lines: 1-59
- SHA256: 2959c104bde3b110fe45f5f117e22d08db1e702456945c2a7e4939de3b0e51cd

```md
## ADDED Requirements

### Requirement: Marketplace 订阅入口
系统 MUST 支持通过 marketplace subscription（市场订阅）发布和验证 Agent Guard Plugin（代理守卫插件），并覆盖 personal marketplace（个人市场）和 repo marketplace（仓库市场）。

#### Scenario: 个人市场条目
- **WHEN** installer（安装器）为 personal scope（个人作用域）执行 dry-run（试运行）、install（安装）或 verify（验证）
- **THEN** 它使用 personal marketplace（个人市场）位置，并把 `agent-guard` 条目解析为 personal plugin package（个人插件包）

#### Scenario: 仓库市场条目
- **WHEN** installer（安装器）为 repo scope（仓库作用域）执行 dry-run（试运行）、install（安装）或 verify（验证）
- **THEN** 它使用当前仓库的 Codex `.agents/plugins/marketplace.json` 和 Claude `.claude-plugin/marketplace.json`，并把 `agent-guard` 条目解析为 `./plugins/agent-guard`

#### Scenario: GitHub 发布分支订阅
- **WHEN** 生成或验证正式 marketplace subscription（市场订阅）说明
- **THEN** 订阅源指向 GitHub repo（GitHub 仓库）的 `marketplace` 发布分支，不使用 tag（标签）或 commit（提交）固定版本

### Requirement: Marketplace 条目契约
系统 MUST 为 Agent Guard Plugin（代理守卫插件）生成和验证包含 `source`、`policy` 和 `category` 的 marketplace entry（市场条目）。

#### Scenario: 生成 Codex 本地条目
- **WHEN** installer（安装器）写入 marketplace entry（市场条目）
- **THEN** 条目包含 `name: agent-guard`、`source.source: local`、`source.path: ./plugins/agent-guard`、`policy.installation`、`policy.authentication` 和 `category`

#### Scenario: 生成 Claude 仓库目录
- **WHEN** installer（安装器）写入 Claude repo marketplace catalog（仓库市场目录）
- **THEN** `.claude-plugin/marketplace.json` 包含 `agent-guard` 插件条目，并把插件目录解析到 `plugins/agent-guard`

#### Scenario: 验证条目
- **WHEN** installer（安装器）验证 marketplace entry（市场条目）
- **THEN** 它拒绝缺少 `source` 对象、`policy.installation`、`policy.authentication` 或 `category` 的旧格式条目

### Requirement: 插件包自包含
系统 MUST 让 `plugins/agent-guard` 成为 Codex 和 Claude 都可安装的自包含 plugin package（插件包）。

#### Scenario: 自包含资源
- **WHEN** package verification（包验证）检查 Agent Guard Plugin（代理守卫插件）
- **THEN** skills（技能）、hooks（钩子）、runtime（运行时）、scripts（脚本）、assets（资源）以及 `.codex-plugin/plugin.json` 和 `.claude-plugin/plugin.json` 都位于 `plugins/agent-guard` 内

## MODIFIED Requirements

### Requirement: 授权插件安装器
系统 MUST 让插件安装保持显式、目标明确、可验证，并以 dry-run（试运行）作为安全默认行为。

#### Scenario: 试运行
- **WHEN** installer（安装器）在没有 install authorization（安装授权）的情况下被调用
- **THEN** 它报告计划写入或验证的 Codex 和 Claude plugin package（插件包）位置、personal marketplace（个人市场）位置和 repo marketplace（仓库市场）位置，不修改 user-level plugin locations（用户级插件位置）或 marketplace files（市场文件）

#### Scenario: 授权安装
- **WHEN** installer（安装器）收到明确 target（目标）、scope（作用域）和 install authorization（安装授权）
- **THEN** 它安装或更新对应 plugin package（插件包）和 marketplace entry（市场条目），并可以验证 manifest（清单）、hook（钩子）、runtime（运行时）、Skill（技能）入口和 marketplace entry（市场条目）可用

#### Scenario: 产品目标校验
- **WHEN** installer（安装器）以 `target: codex`、`target: claude` 或 `target: all` 运行
- **THEN** 它分别校验 `.codex-plugin/plugin.json`、`.claude-plugin/plugin.json` 或两者，并且不把 Claude Junction（Claude 目录联接）作为兼容条件

#### Scenario: 作用域校验
- **WHEN** installer（安装器）以 `scope: personal`、`scope: repo` 或 `scope: all` 运行
- **THEN** 它分别验证 personal marketplace（个人市场）、repo marketplace（仓库市场）或两者，并且不写入 Guard Profile（守卫画像）、project hooks（项目钩子）或 git config（Git 配置）
```

## openspec/changes/agent-guard-marketplace-subscription/specs/agent-guard-skill-entrypoints/spec.md

- Source: openspec/changes/agent-guard-marketplace-subscription/specs/agent-guard-skill-entrypoints/spec.md
- Lines: 1-25
- SHA256: 2aee9a59ddfa4d50c9690814b42c13802b1cd85a21752faaf978e185826b28bc

```md
## ADDED Requirements

### Requirement: 用户级 Skill 安装兼容层移除
系统 MUST 不再把 user-level Skill installation（用户级技能安装）、Claude Junction（Claude 目录联接）或旧 install scripts（安装脚本）作为 Agent Guard Plugin（代理守卫插件）的发布、订阅或验证契约。

#### Scenario: 扫描旧安装脚本
- **WHEN** 检查仓库发布入口
- **THEN** `scripts/install/install_user_skill.ps1`、`scripts/install/sync_claude_junction.ps1` 和 `scripts/install/verify_install.py` 不作为 Agent Guard 安装入口存在

#### Scenario: 验证发布契约
- **WHEN** Agent Guard Plugin（代理守卫插件）发布契约被验证
- **THEN** 验证只依赖 plugin package（插件包）、marketplace entry（市场条目）、manifest（清单）、hooks（钩子）、runtime（运行时）和 Skill（技能）入口，不依赖 `.agents/skills/agent-guard` 或 `.claude/skills/agent-guard` Junction（目录联接）

## MODIFIED Requirements

### Requirement: 共享核心资源
系统 MUST 把共享 scripts（脚本）、assets（资源）和 common references（通用参考资料）保留在核心 `agent-guard` Skill（技能）区域，同时让场景化入口引用这些共享资源而不是复制它们。

#### Scenario: 场景入口使用共享脚本
- **WHEN** 场景化入口需要共享 script（脚本）或 template（模板）
- **THEN** 它通过相对路径引用共享核心资源，而不是复制资源目录

#### Scenario: 插件包验证
- **WHEN** Agent Guard Plugin package verification（插件包验证）运行
- **THEN** 它检查核心共享资源、四个场景化入口、产品 manifest（清单）和 marketplace subscription（市场订阅）契约，而不是检查 user-level Skill installation（用户级技能安装）
```

