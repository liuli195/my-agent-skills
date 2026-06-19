# Brainstorm Summary

- Change: add-comet-agent-review-gate
- Date: 2026-06-19

## 已确认事实

- 目标是在 Comet build 完成后、verify 前增加 agent review gate。
- 不新增 Comet phase，不修改原始 `/comet` 阶段链。
- reviewed flow 是可选增强入口，原始 Comet 流程仍可用。
- 门禁必须使用 Gate Binding，不能复用 Session Focus Binding。
- 门禁证据是跨 agent review 生成的 `review-pass.json`。
- `review-pass.json` 必须校验 `status`、`change`、`head_ref`、`blocking_findings`、`report`、`report_hash`。
- 本 change 依赖 `add-cross-agent-review-mechanism` 和 `add-guard-gate-binding` 的契约。
- 横向读取 3 个 active changes 后确认：`add-cross-agent-review-mechanism` 只产出 review report/pass marker；`add-guard-gate-binding` 只提供 gate activation/completion；`add-comet-agent-review-gate` 是下游集成层，负责把两者接入 Comet build→verify 间隙。
- `add-comet-agent-review-gate/design.md` 已明确倾向“新增 reviewed flow wrapper，而不是修改 Comet 主入口”。因此不应把 review gate 塞进普通 `/comet` 默认路径。

## 候选技术方案

- 候选 A：新增独立 reviewed wrapper，例如 `/comet-reviewed`，串联 build complete → cross-agent review → gate completion → `/comet-verify`。
- 候选 B：新增 Agent Guard profile/template + 文档化命令流，不做 wrapper 自动化。
- 候选 C：在现有 `/comet` 中加入可选开关，但不改变 phase。

## 待确认

- wrapper 命名仍待确认：`/comet-reviewed` 更符合既有设计里的 reviewed flow 概念；`/comet-agent-review-gate` 更精确但偏内部。

## 风险

- 另外两个前置 change 未实现时，本 change 的实现只能基于稳定契约；build 阶段必须按依赖状态拆任务或阻塞。
- 如果 reviewed wrapper 自动启动 `/comet-verify`，需要明确 gate failure 时只停在 verify 前，不写 Comet phase。

## 测试策略候选

- 用 CLI/integration tests 覆盖 review fail、missing `review-pass.json`、stale `head_ref`、review pass 启动 verify handoff。
- 用 profile validator/runtime tests 验证 Guard Profile sample 的 JSON artifact checks。

## Spec Patch

暂未发现必须回写的 delta spec 变更。
