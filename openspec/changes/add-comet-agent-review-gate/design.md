## Context

Comet 的核心阶段链是 `open -> design -> build -> verify -> archive`。用户希望在 build 和 verify 之间增加跨 agent review，但不希望改动 Comet phase，也不希望 Agent Guard 承担 review 逻辑。

前置 change 提供三块能力：JSON artifact 内容校验、Gate Binding、跨 agent review pass marker。本 change 只负责把这些能力集成到 Comet reviewed flow（带审查的流程）。

## Goals / Non-Goals

**Goals:**

- 在 Comet build 完成后、verify 前增加外部门禁。
- 使用 Gate Binding 绑定 `before_verify` 门禁。
- 使用跨 agent review 产出的 `review-pass.json` 作为门禁证据。
- 使用 Agent Guard JSON artifact checks 校验 pass marker 内容。
- 保持原始 `/comet` 流程可用，不强制所有 Comet change 使用 review gate。

**Non-Goals:**

- 不新增 Comet phase。
- 不修改 `.comet.yaml` 主状态机字段表达 review 状态。
- 不让 Agent Guard 派发 reviewer agent。
- 不把 review report 内容解析逻辑写入 Comet。

## Decisions

1. 新增 reviewed flow wrapper，而不是修改 Comet 主入口。

   例如 `/comet-reviewed` 或文档化包装流程负责串联 build、review、gate completion、verify。原 `/comet` 行为保持不变。

2. Gate subject key 包含 change 和 head。

   建议 subject key 使用 `repo + change_id + head_ref`。这样旧 review pass marker 不能放行新 HEAD。

3. Guard Profile 只检查 pass marker。

   Comet review gate 的 Guard Profile 检查 `review-pass.json` 的 `status`、`change`、`head_ref`、`blocking_findings`、`report` 和 `report_hash`。它不读取 reviewer 原始判断。

4. Review fail 回 build，verify 不启动。

   review 不通过时流程停在 verify 前，用户回 build 修复或重新 review。

## Risks / Trade-offs

- 包装入口和原 `/comet` 并存可能让用户困惑 -> 文档明确 reviewed flow 是可选增强，不是 Comet phase。
- head_ref 获取不一致 -> wrapper 统一取当前 Git HEAD 并写入 subject key 和 pass marker。
- 前置能力未完成时无法集成 -> tasks 明确依赖前三个 change。

## Migration Plan

1. 等前三个 change 归档或至少合入后再实现本 change。
2. 新增 sample Guard Profile 或模板。
3. 新增 reviewed flow wrapper 或操作文档。
4. 跑集成测试覆盖 review fail、review pass、stale marker 和 verify handoff。

## Open Questions

包装入口命名待实现阶段确认，候选为 `/comet-reviewed` 或 `/comet-agent-review-gate`。
