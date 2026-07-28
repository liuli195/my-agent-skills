# Comet Spec Context

- Change: simplify-release-flow
- Phase: design
- Mode: beta
- Context hash: aa448e3dd899b463b4b3c953da91faabca2263869554bc4a5180d1d8169e8744

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This beta context pack verbatim-projects spec files and references supporting artifacts by hash, not an agent-authored summary.

## Source References

- Source: openspec/changes/simplify-release-flow/proposal.md
- SHA256: e650e2f96b5283034742f58bbd0fa0ca2c8acb43e5a7fdcaaa0d9eee70995d81
- Source: openspec/changes/simplify-release-flow/design.md
- SHA256: 3cfa74b356d91be5d8785e7ef003ab3168f5e904adbbd42e1ffb1587404d3b0f
- Source: openspec/changes/simplify-release-flow/tasks.md
- SHA256: a5c99f99e23590a5f1e96aa3b8c0d7791f373bbac8a737acbba6a1146450044c
- Source: openspec/changes/simplify-release-flow/specs/release-flow-plugin/spec.md
- SHA256: 6ef6b65e20af714d90269a81f16553f588c5bac8cd1283adfd02e3c12aa620cb

## Acceptance Projection

## openspec/changes/simplify-release-flow/specs/release-flow-plugin/spec.md

- Source: openspec/changes/simplify-release-flow/specs/release-flow-plugin/spec.md
- Lines: 1-241
- SHA256: 6ef6b65e20af714d90269a81f16553f588c5bac8cd1283adfd02e3c12aa620cb

```md
## ADDED Requirements

### Requirement: 插件发布清单单一注册表

系统 MUST 使用单一 Plugin registry（插件注册表）描述可发布插件，并从该注册表推导 projection（投影）校验、Codex marketplace（Codex 市场）生成和 manifest（插件清单）路径。

#### Scenario: 新增插件只需注册一次

- **WHEN** 维护者把插件加入发布范围
- **THEN** 系统 MUST 只要求在单一 Plugin registry（插件注册表）中声明该插件
- **THEN** projection（投影）校验、marketplace（市场）生成和 manifest（插件清单）版本检查 MUST 使用同一声明

#### Scenario: projection 插件未注册

- **WHEN** `.release-flow/projection.yaml`（投影配置）引用未注册插件
- **THEN** preflight（发布前检查）和 CI（持续集成）发布 MUST 拒绝继续
- **THEN** 错误 MUST 指出未注册插件名

### Requirement: 发布输入选择提升插件

系统 MUST 使用 `bumpPlugins`（提升插件列表）声明本次发布需要提升版本的插件。

版本漂移比较基准 MUST 是远端发布通道 `origin/<channelBranch>`（远端通道分支）中同路径 manifest（插件清单）的版本。

#### Scenario: 只提升部分插件

- **WHEN** `bumpPlugins`（提升插件列表）只包含部分插件
- **THEN** preflight（发布前检查）MUST 只要求这些插件的 manifest（插件清单）版本等于发布版本
- **THEN** 未声明插件的 manifest（插件清单）版本 MUST 等于远端发布通道同路径 manifest（插件清单）版本

#### Scenario: 不提升插件

- **WHEN** `bumpPlugins`（提升插件列表）为空列表
- **THEN** preflight（发布前检查）MUST 不要求任何插件 manifest（插件清单）版本等于发布版本
- **THEN** 任何 manifest（插件清单）版本与远端发布通道同路径 manifest（插件清单）版本不一致 MUST 被拒绝

#### Scenario: 未声明提升导致版本漂移

- **WHEN** 某个插件 manifest（插件清单）版本不同于远端发布通道同路径版本但不在 `bumpPlugins`（提升插件列表）中
- **THEN** preflight（发布前检查）MUST 拒绝继续
- **THEN** 错误 MUST 指出该插件需要加入 `bumpPlugins`（提升插件列表）或撤回版本变更

#### Scenario: 未声明新插件

- **WHEN** 某个插件在远端发布通道没有同路径 manifest（插件清单）且不在 `bumpPlugins`（提升插件列表）中
- **THEN** preflight（发布前检查）MUST 拒绝继续
- **THEN** 错误 MUST 指出该插件需要加入 `bumpPlugins`（提升插件列表）

### Requirement: 远端发布冲突检查

系统 MUST 在发布前检查和 CI（持续集成）发布前检查远端 tag（标签）和 GitHub Release（GitHub 发布）是否已存在。

#### Scenario: 远端 tag 已存在

- **WHEN** 远端已存在本次发布 tag（标签）
- **THEN** preflight（发布前检查）和 CI（持续集成）发布 MUST 拒绝继续
- **THEN** 输出 MUST 明确报告 release already exists（发布已存在）

#### Scenario: GitHub Release 已存在

- **WHEN** GitHub Release（GitHub 发布）已存在本次发布 tag（标签）
- **THEN** preflight（发布前检查）和 CI（持续集成）发布 MUST 拒绝继续
- **THEN** 输出 MUST 明确报告 release already exists（发布已存在）

### Requirement: 发布投影只在隔离发布环境执行

系统 MUST NOT 要求维护者在源码分支运行正式 marketplace（市场）projection（投影）。

#### Scenario: 本地源码分支保持 DEV 身份

- **WHEN** 维护者在源码分支执行发布前检查
- **THEN** preflight（发布前检查）MUST NOT 要求运行本地 `project`（投影）命令
- **THEN** 源码分支中的 DEV（开发）marketplace（市场）配置 MUST 保持不变

#### Scenario: CI 生成正式发布投影

- **WHEN** GitHub Workflow（GitHub 工作流）执行发布
- **THEN** CI（持续集成）MUST 在隔离发布树中应用正式 marketplace（市场）projection（投影）
- **THEN** 正式 marketplace（市场）身份 MUST 只写入发布通道产物

## MODIFIED Requirements

### Requirement: 发布流程配置

系统 MUST 使用 `.release-flow/config.yaml` 保存项目级发布流程配置，并将该文件纳入 Git 版本管理。

#### Scenario: 声明发布通道

- **WHEN** 项目配置声明 release（发布）信息
- **THEN** 配置 MUST 声明 source ref（源引用）、channel branch（通道分支）和 branch mode（分支模式）
- **THEN** branch mode MUST 支持 `remote-only`，表示本地不创建发布分支

#### Scenario: 声明 workflow 触发方式

- **WHEN** 项目配置声明 workflow（工作流）
- **THEN** 配置 MUST 声明 GitHub Workflow 文件路径
- **THEN** 配置 MUST 声明触发方式为 `workflow_dispatch`

#### Scenario: 不声明本地发布记录目录

- **WHEN** 项目配置声明 release-flow（发布流程）设置
- **THEN** 配置 MUST NOT 声明本地 release record（发布记录）目录
- **THEN** 发布流程 MUST NOT 依赖 `.release-flow/releases/<tag>/` 持久目录

#### Scenario: 不声明 GitHub Rulesets 期望设置

- **WHEN** 项目配置声明 GitHub 仓库设置
- **THEN** 配置 MUST NOT 声明 GitHub Rulesets（GitHub 规则集）期望
- **THEN** preflight（发布前检查）MUST NOT 检查 GitHub Rulesets（GitHub 规则集）

### Requirement: 项目启用阶段

系统 MUST 提供 project setup（项目启用）阶段，用于生成目标项目配置，并输出 GitHub Actions（GitHub 自动化任务）权限配置方案。首版 MUST NOT 在没有额外实现仓库上下文和认证回读前修改 GitHub 仓库设置。

#### Scenario: 生成目标项目配置

- **WHEN** 用户在目标项目启用 release-flow（发布流程）
- **THEN** 系统 MUST 生成 `.release-flow/config.yaml`（配置文件）
- **THEN** 系统 MUST 生成 `.release-flow/projection.yaml`（投影配置）
- **THEN** 系统 MUST 从插件模板生成目标项目的薄 GitHub Workflow（GitHub 工作流）入口
- **THEN** 系统 MUST NOT 生成只服务本地 release record（发布记录）的 `.release-flow/.gitignore`
- **THEN** 系统 MUST NOT 将插件内的发布脚本复制到目标项目仓库
- **THEN** 系统 MUST NOT 创建 `.release-flow/releases/<tag>/release-plan.json`（发布计划文件）

#### Scenario: 生成 GitHub 配置方案

- **WHEN** 项目启用阶段检查 GitHub 仓库
- **THEN** 系统 MUST 输出 Actions permissions（自动化任务权限）的期望配置方案
- **THEN** 系统 MUST NOT 输出 GitHub Rulesets（GitHub 规则集）的期望配置方案
- **THEN** 系统 MUST NOT 输出非敏感 marketplace identity（市场身份）的 GitHub Actions Variables（GitHub 变量）配置方案

#### Scenario: 授权后修改 GitHub 配置

- **WHEN** 用户明确授权自动配置 GitHub
- **THEN** 首版系统 MUST 报告自动写入 GitHub 暂不可用
- **THEN** 系统 MUST NOT 调用真实 GitHub 设置 API（接口）
- **THEN** 后续版本 MAY 使用 `gh`（GitHub 命令行）或 GitHub API（接口）修改仓库设置并回读验证结果

#### Scenario: 未授权时输出手动步骤

- **WHEN** 用户未授权自动配置 GitHub
- **THEN** 系统 MUST 输出用户可手动执行的 Actions permissions（自动化任务权限）配置步骤
- **THEN** 系统 MUST NOT 输出 GitHub Rulesets（GitHub 规则集）配置步骤
- **THEN** 系统 MUST NOT 修改 GitHub 仓库设置

### Requirement: 发布前检查

系统 MUST 提供 release-flow preflight（发布前检查）阶段，用于在发布前验证本地配置、发布输入、manifest（插件清单）、发布投影和远端发布冲突。

#### Scenario: 检查配置文件

- **WHEN** 执行 preflight（发布前检查）
- **THEN** 系统 MUST 验证 `.release-flow/config.yaml`（配置文件）存在且合法
- **THEN** 系统 MUST 验证 `.release-flow/projection.yaml`（投影配置）存在且合法

#### Scenario: 检查发布输入

- **WHEN** 执行 preflight（发布前检查）
- **THEN** 系统 MUST 验证 `tag`（标签）和 `version`（版本）一致
- **THEN** 系统 MUST 验证 `bumpPlugins`（提升插件列表）存在且只包含已注册插件

#### Scenario: 检查版本一致性

- **WHEN** 执行 preflight（发布前检查）
- **THEN** 系统 MUST 只要求 `bumpPlugins`（提升插件列表）声明的插件 manifest（插件清单）版本等于发布版本
- **THEN** 系统 MUST 拒绝未声明插件的 manifest（插件清单）版本不同于远端发布通道同路径版本

#### Scenario: 检查发布投影

- **WHEN** 执行 preflight（发布前检查）
- **THEN** 系统 MUST 验证 projection（投影）可以由单一 Plugin registry（插件注册表）生成
- **THEN** 系统 MUST 拒绝无法生成的发布投影
- **THEN** 系统 MUST NOT 要求用户在源码分支运行正式 marketplace（市场）projection（投影）

#### Scenario: 检查远端发布冲突

- **WHEN** 执行 preflight（发布前检查）
- **THEN** 系统 MUST 检查远端 tag（标签）是否已存在
- **THEN** 系统 MUST 检查 GitHub Release（GitHub 发布）是否已存在
- **THEN** 任一已存在时 MUST 拒绝继续

#### Scenario: 不检查 GitHub Rulesets

- **WHEN** 执行 preflight（发布前检查）
- **THEN** 系统 MUST NOT 读取 GitHub Rulesets（GitHub 规则集）
- **THEN** 系统 MUST NOT 声称已验证 GitHub Rulesets（GitHub 规则集）

### Requirement: 发布执行阶段

系统 MUST 提供 release-flow publish（发布）阶段，通过 GitHub Workflow（GitHub 工作流）执行发布，本地不得执行发布 Git（版本管理）写操作。

#### Scenario: 本地只触发 workflow

- **WHEN** 用户执行 publish（发布）
- **THEN** 本地系统 MUST 使用 `workflow_dispatch`（工作流触发）触发 GitHub Workflow（GitHub 工作流）
- **THEN** 本地系统 MUST 只传递 `tag`（标签）、`version`（版本）和 `bumpPlugins`（提升插件列表）
- **THEN** 本地系统 MUST NOT 创建发布分支
- **THEN** 本地系统 MUST NOT 创建 tag（标签）
- **THEN** 本地系统 MUST NOT push（推送）发布内容

#### Scenario: 发布试运行输出明确字段

- **WHEN** 用户执行 `publish --dry-run`（发布试运行）
- **THEN** 输出 MUST 包含 release tag（发布标签）
- **THEN** 输出 MUST 包含 `git_tag_created: false`
- **THEN** 输出 MUST 包含 `local_branch_created: false`
- **THEN** 输出 MUST 包含 `push_run: false`

#### Scenario: GitHub Workflow 执行发布

- **WHEN** GitHub Workflow（GitHub 工作流）运行
- **THEN** workflow（工作流）MUST checkout（检出）配置指定的 source ref（源引用）
- **THEN** workflow（工作流）MUST 直接运行 source repo（源码仓库）内的 release-flow（发布流程）脚本
- **THEN** workflow（工作流）MUST 读取 source repo（源码仓库）内的 `.release-flow/projection.yaml`（投影配置）
- **THEN** workflow（工作流）MUST 在隔离发布树中应用 projection（投影）
- **THEN** workflow（工作流）MUST 创建或更新远端 `marketplace`（市场分支）
- **THEN** workflow（工作流）MUST 创建 tag（标签）
- **THEN** workflow（工作流）MUST 创建 GitHub Release（GitHub 发布）
- **THEN** `ci-publish`（持续集成发布）MUST NOT 提供 `--dry-run`（试运行）分支逻辑

#### Scenario: CI 输出发布追溯字段

- **WHEN** GitHub Workflow（GitHub 工作流）发布成功
- **THEN** 输出 MUST 包含 release URL（发布链接）
- **THEN** 输出 MUST 包含 marketplace commit（市场提交）
- **THEN** 输出 MUST 包含 tag commit（标签提交）
- **THEN** 输出 MUST 包含 workflow run URL（工作流运行链接）

## REMOVED Requirements

### Requirement: 单次发布初始化阶段

**Reason**: 本地 release-plan（发布计划）让流程多一步，并在 CI（持续集成）里重复生成，成本高于收益。

**Migration**: 用户直接运行 preflight（发布前检查）和 publish（发布），发布输入由 `tag`、`version` 和 `bumpPlugins`（提升插件列表）提供。`release-init`（发布初始化）命令、文档、模板和测试引用 MUST 删除。

### Requirement: 发布记录与总结

**Reason**: 本地 release record（发布记录）和 `summarize`（发布摘要）反复产生 ignored（忽略）残留和手工补字段成本。

**Migration**: CI（持续集成）发布完成后直接输出 release URL（发布链接）、marketplace commit（市场提交）、tag commit（标签提交）和 workflow run URL（工作流运行链接）。仅服务 `.release-flow/releases/`（发布记录目录）的 `.release-flow/.gitignore` MUST 删除。
```

Full source files remain canonical. If a required heading or scenario is missing here, regenerate the handoff or read the source spec directly. Supporting files (proposal, design, tasks) are referenced by hash only.
