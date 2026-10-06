## Context

Comet 的核心阶段链是 `open -> design -> build -> verify -> archive`。用户希望在 build 和 verify 之间增加跨 agent review，但不希望改动 Comet phase，也不希望 Agent Guard 承担 review 逻辑。

前置 change 提供三块能力：JSON artifact 内容校验、Global Command Guard（全局命令守卫点）、跨 agent review pass marker。本 change 只负责把这些能力集成到 Comet build -> verify 边界。

## Goals / Non-Goals

**Goals:**

- 在 Comet build 完成后、verify 前增加外部门禁。
- 使用用户级 Global Command Guard 拦截 `comet-guard.sh <change> build --apply`。
- 使用跨 agent review 产出的 `review-pass.json` 作为门禁证据。
- 通过 Agent Guard `artifacts.yaml` 产物注册层引用 cross-agent-review 默认输出目录下的 pass marker。
- 使用 Agent Guard JSON predicate checks 校验 pass marker 内容。
- 保持原始 Comet 阶段链不变；只有安装并启用匹配的用户级 Global Command Guard 时才触发 review gate。
- 更新 Agent Guard Skill 入口说明和共享参考文档，使 Global Command Guard 可被正确安装、同步、运行反馈和排障。

**Non-Goals:**

- 不新增 Comet phase。
- 不新增 reviewed wrapper。
- 不修改 `.comet.yaml` 主状态机字段表达 review 状态。
- 不让 Agent Guard 派发 reviewer agent。
- 不把 review report 内容解析逻辑写入 Comet。
- 不修改 cross-agent-review 默认输出目录或边界行为。

## Decisions

1. 不新增 wrapper，由 Global Command Guard 拦截 build 完成边界。

   主拦截点是 `comet-guard.sh <change> build --apply`。该命令位于 build 完成、phase 进入 verify 之前，符合“进入 verify 前拦截”。`comet-guard.sh <change> verify --apply` 属于 verify 完成后的状态推进，不作为主要拦截点。命令模式必须覆盖直接调用、脚本路径调用和 `"$COMET_BASH" "$COMET_GUARD" <change> build --apply` 这类环境变量调用形态。

2. 用户级静态规则，项目级运行态。

   Comet review gate 的 Guard Profile 作为用户级全局守卫配置，静态文件位于 `~/.agents/guards/<profile_id>/global-command-guards.yaml`。但它拦截的是项目命令，因此 audit 和产物解析按项目运行态执行，不写入 `~/.agents/guard`。

3. 通过产物注册层引用 pass marker。

   `artifacts.yaml` 注册 `cross_agent_review_pass`，路径指向 `.local/cross-agent-review/{change}/{git_head}/review-pass.json`。Global Command Guard 通过 `artifact` / `artifact_id` reference 读取该产物，并检查 `status`、`change`、`head_ref`、`blocking_findings`、`report` 和 `report_hash`。它不读取 reviewer 原始判断，不使用独立 `evidence.path`，也不要求把 pass marker 复制到 `.local/guard/evidence`。

   对用户级 profile 中的相对 artifact path，Runtime 必须按当前项目根目录解析；不能解析到用户 profile 目录或 `~/.agents/guard`。Global Command Guard 可使用 `{change}`、`{git_head}`、`{source_scope}`、`{profile_id}`、`{guard_id}`、`{effective_guard_id}`、`{runtime_scope}`，但该路径不能强制依赖 Session Focus 专用的 `{instance_id}` / `{state_version}`。

4. Review fail 表现为无有效 pass marker，build 完成不放行。

   review 不通过时 cross-agent-review 不生成 pass marker，Global Command Guard 继续拒绝 build 完成命令。后续修复或重新 review 的具体流程由调用方和 cross-agent-review Skill 决定，不写入 Agent Guard。

5. Deny 输出由画像配置承载，不承载内置 review flow。

   Global Command Guard 在 `build --apply` 执行前拦截，但 Agent Guard 只返回结构化 deny：`reason`、`next`、`suggestion`、captures、failing guards 和 artifact/evidence 详情。`reason`、`next`、`suggestion` 可由 Guard Profile 场景化配置提供，Runtime 只按通用机制透传或渲染。build readiness、cross-agent-review 输入准备、worktree clean、测试结果文件和 reviewer 派发属于调用方与 cross-agent-review Skill 的契约，不写入 Agent Guard Runtime 或 Agent Guard Skill 流程。

6. Agent Guard skill entrypoints 必须覆盖全局命令守卫。

   当前 Runtime README 已描述 Global Command Guard，但 `$agent-guard`、`$agent-guard-install`、`$agent-guard-init`、`$agent-guard-update`、`$agent-guard-run` 和共享模板索引缺少对应说明。本 change 必须补齐这些入口文档，避免能力只存在于内部实现。文档更新必须符合四条标准：渐进式披露、按 agent 使用场景组织、明确禁止项、语言简洁高效。

## Risks / Trade-offs

- 拦截点错误会导致 review 太晚才发生 -> 主拦截点固定为 build 阶段 `--apply`，并明确 verify 阶段 `--apply` 不是主要拦截点。
- Global Command Guard 当前尚未复用 `artifacts.yaml` 产物注册层 -> 需要小改动把 artifact reference 接到全局命令守卫评估路径；如果不能纯配置实现，必须先提交原因和修改点给用户评审。
- head_ref 获取不一致 -> Global Command Guard 使用当前 Git HEAD，cross-agent-review pass marker 也必须匹配该 HEAD。
- Agent Guard 深入业务流程会造成后续每个守卫点都要在 Agent Guard 中新增流程分支 -> 核心规则要求 Agent Guard 只做通用守卫机制；场景化 deny 提示保留在 Guard Profile 配置中，业务流程保留在调用方或对应 Skill 中。
- 命令匹配过窄可能漏过真实 `/comet` 调用 -> profile sample 必须覆盖直接脚本、路径脚本和 `$COMET_GUARD` 变量调用形态。
- Agent Guard skill 文档遗漏或组织混乱会导致用户无法正确维护全局守卫 -> 本 change 明确要求更新所有相关入口说明和模板索引，并按 agent 场景渐进披露。

## Migration Plan

1. 更新当前 delta spec、proposal、design 和 tasks，移除 Gate Binding / wrapper 方向。
2. 新增用户级 Guard Profile sample 或模板。
3. 让 Global Command Guard 通过 `artifacts.yaml` 引用 cross-agent-review 默认输出，并按项目根解析用户级 profile 中的相对 artifact path。
4. 在 deny 输出和文档中写清通用失败字段、artifact/evidence 详情和 profile 声明的下一步提示；Runtime 只透传或渲染这些配置字段，不写入 cross-agent-review 内部流程。
5. 更新 Agent Guard skill 入口说明和共享参考文档。
6. 跑集成测试覆盖 missing/invalid/pass/stale pass marker、命令模式变体和 Agent Guard 不改变 Comet phase 语义。

## Open Questions

无。wrapper 已明确不做。
