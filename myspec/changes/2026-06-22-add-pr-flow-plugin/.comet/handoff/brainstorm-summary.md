# Brainstorm Summary

- Change: add-pr-flow-plugin
- Date: 2026-06-22
- Status: 已确认

## 已确认的产品边界

- `pr-flow` Plugin（插件）服务个人仓库的 PR Flow（拉取请求流程）。
- 首版保留 `complete`、`cleanup`、`diagnose`、`init`、`hotfix` 和 `tweak`。
- 删除 dry-run（试运行）机制。
- `init` 不自动写 GitHub Rulesets（GitHub 规则集），只生成本地配置和建议。
- 不做 Branch Protection（分支保护）回退、Issue（议题）绑定、GitHub workflow（工作流）生成。
- authorization phrase（授权短语）只替代“我确认”，不改变原流程授权边界。

## 确认的技术方案

采用多入口 Skill（技能）加共享脚本内核：

- `pr-flow` 作为总入口和 diagnose。
- `pr-flow-init` 生成 `.pr-flow/config.yaml`、PR body template 和 Rulesets 建议。
- `pr-flow-complete` 负责创建或同步 PR、等待 checks、执行 review gate、合并和 cleanup。
- `pr-flow-cleanup` 独立覆盖 #51。
- `pr-flow-hotfix` 处理显式允许目标分支的紧急直推。
- `pr-flow-tweak` 处理跳过 review gate 的小改动 PR。
- `plugins/pr-flow/skills/*/scripts/pr_flow.py` 承担确定性命令逻辑。

## 关键取舍与风险

- 不做 dry-run：减少双路径复杂度；安全边界改由 diagnose、前置检查、stop state 和执行后回读承担。
- 不自动写 Rulesets：避免低频远端治理拖重首版；init 输出可人工或 agent 执行的建议。
- hotfix 直推风险高：用目标分支 allow-list、基线一致检查、验证命令、授权短语和远端回读控制。
- tweak 不限制文件范围：保持个人仓库轻量；必须提供 reason 并写入 PR body。
- local review evidence 首版只接 `cross-agent-review`：避免过早建设通用证据平台。

## 测试策略

- 配置测试：init 生成 config、template、gitignore 和 Rulesets 建议，不写远端。
- diagnose 测试：覆盖 `PUSH_REQUIRED`、`DISPATCH_REQUIRED`、`REPLY_OR_FIX_REQUIRED`、`EXCEPTION_REQUIRED`。
- lifecycle 测试：创建/同步 PR、checks 轮询、review gate、head-locked merge 和 cleanup 编排。
- cleanup 测试：覆盖 #51 成功路径和未合并 PR、dirty worktree、分支不匹配等拒绝场景。
- hotfix 测试：覆盖 allow-list、基线一致、验证命令、授权短语、push 后回读。
- tweak 测试：覆盖 reason 必填、PR body 标记、跳过 review gate 但保留 checks/merge/cleanup。
- package 测试：Codex/Claude manifest 和 release projection 包含 `pr-flow`。

## Spec Patch

无。当前 delta spec 已覆盖本轮确认范围。

## 待确认问题

- `cross-agent-review` evidence 默认路径是固定约定，还是配置项。
- required checks（必需检查）由用户手写配置，还是 init 给候选建议但不自动写入。
