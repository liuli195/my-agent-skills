## Context

`complete`（收尾）和 `tweak`（小改）已经共用 `run_lifecycle`（运行生命周期），但生命周期入口在 push（推送）准备阶段按命令分叉：`complete`（收尾）使用 `auto_push_current_branch_if_needed`（按需自动推送），`tweak`（小改）在没有 PR（拉取请求）时使用旧的 `missing_upstream_state`（缺少上游分支状态）。

`ruleset_merge_blocking`（规则集阻止合并）恢复路径已能复用 checks（检查）等待并重试 merge（合并），但旧设计明确不启用 GitHub auto-merge（自动合并）。实际 PR（拉取请求）运行显示 GitHub CLI（GitHub 命令行）会给出 `--auto`（自动合并）恢复建议，手工执行后可继续。

## Goals / Non-Goals

**Goals:**

- 让 `tweak`（小改）与 `complete`（收尾）共用 safe auto-push（安全自动推送）能力。
- 保留 `tweak`（小改）的唯一差异：跳过 review gate（审查门禁）。
- 在 ruleset（规则集）阻止普通 merge（合并）且 GitHub CLI（GitHub 命令行）明确建议 `--auto`（自动合并）时，复用现有 merge（合并）命令追加 `--auto`（自动合并）重试一次。

**Non-Goals:**

- 不新增依赖。
- 不新增 `.pr-flow/config.yaml`（配置文件）字段。
- 不使用 `--admin`（管理员绕过）。
- 不重写 PR Flow（拉取请求流程）状态机。

## Decisions

1. `tweak`（小改）复用现有 auto-push（自动推送）函数。

   `run_lifecycle`（运行生命周期）把 `complete`（收尾）专属判断改成 `command in {"complete", "tweak"}`。这样 push（推送）安全边界仍由同一个函数负责：工作区必须干净、当前分支不能是 base branch（目标分支）、远端 active rules（有效规则）必须为 0。

2. 停止让 `tweak`（小改）走旧 `missing_upstream_state`（缺少上游分支状态）。

   该函数只表达“缺少 upstream（上游分支）就停下让用户 push（推送）”，已经被更完整的 auto-push（自动推送）门禁替代。保留它只会让 `complete`（收尾）和 `tweak`（小改）继续分叉。

3. `--auto`（自动合并）只作为 ruleset（规则集）恢复动作。

   不把 `--auto`（自动合并）设为默认 merge（合并）方式。只有普通 merge（合并）返回 ruleset（规则集）错误，且错误文本包含 GitHub CLI（GitHub 命令行）的 `--auto`（自动合并）建议时，才追加 `--auto`（自动合并）重试。命令仍保留 `--match-head-commit`（匹配头提交）。

## Risks / Trade-offs

- [Risk] `--auto`（自动合并）可能启用 GitHub（代码托管平台）侧等待，而不是立即合并。Mitigation: 只在 GitHub CLI（GitHub 命令行）明确建议时使用；后续仍走现有 cleanup（清理）读回，不新增第二套等待状态。
- [Risk] `tweak`（小改）自动推送扩大了原本的命令行为。Mitigation: 复用 `complete`（收尾）已有安全门禁，不新增第二套规则。
