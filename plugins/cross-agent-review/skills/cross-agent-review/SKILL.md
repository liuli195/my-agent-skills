---
name: cross-agent-review
description: "运行跨代理审查。仅用于 Comet build completion（构建完成）、PR Flow local review（本地审查）或用户显式调用。"
---

# Cross-Agent Review

本 skill 运行独立 cross-agent review（跨代理审查），不推进 Comet phase（阶段），不运行构建或测试，不自动安装 Claude Agent SDK。

## 调用边界（强制）

ONLY ALLOWED:
- Comet build completion（构建完成）阶段：进入 verify（验证）前，生成供 Agent Guard（代理守卫）build gate（构建门禁）使用的 `review-pass.json`。
- PR Flow（拉取请求流程）阶段已启用 local review（本地审查）。
- 用户显式调用 `cross-agent-review`（跨代理审查）。

STRICTLY FORBIDDEN:
- Comet verify（验证）阶段自动调用。
- 通用 code review（代码审查）阶段自动调用。

## 前置条件

- 当前 worktree 必须干净。
- 当前 `HEAD` 必须等于传入的 `--head-ref`。
- 当前 Python、默认 Claude SDK venv，或 `--sdk-python` 指定的 Python 必须能导入 `claude_agent_sdk`。

## 命令

```bash
python scripts/cross_agent_review.py run \
  --change <change-id> \
  --base-ref <base-ref> \
  --head-ref <head-ref> \
  --diff-file <path> \
  --spec-file <path> \
  --design-file <path> \
  --tasks-file <path>
```

## 输入文件准备

`--diff-file`、`--spec-file`、`--design-file` 和 `--tasks-file` 等运行前生成的输入文件，必须放在同一次 review 的 run 目录下：

```text
.local/cross-agent-review/<change>/<head_ref>/prepared-inputs/
```

随后把这些文件路径显式传给命令参数。不要在 `.local/` 下创建独立的输入根目录；review 运行后会把最终输入快照复制到同一 run 目录的 `inputs/`。

输出默认写入 `.local/cross-agent-review/<change>/<head_ref>/`。运行时会先把输入文件快照复制到输出目录下的 `inputs/`：

- `inputs/diff.patch`
- `inputs/spec.md`
- `inputs/design.md`
- `inputs/tasks.md`

## Reviewer 输出契约

Reviewer（审查代理）必须只返回一个 JSON object（JSON 对象），不要返回 Markdown（标记文本）或解释性正文。

每个 finding（发现项）必须包含 `severity`。只允许以下 severity（严重级别）值：

- `CRITICAL`
- `IMPORTANT`
- `WARNING`
- `SUGGESTION`

不要使用 severity aliases（严重级别别名），例如 `high`、`medium`、`low`、`minor` 或 `info`。missing severity（缺少严重级别）和别名都会被视为无效 reviewer 输出，并转成 blocking finding（阻断发现项）。

如果没有问题，返回空 findings（发现项）列表：

```json
{"role":"<role>","status":"completed","findings":[]}
```

只有没有 CRITICAL/IMPORTANT findings（发现项），且 worktree 仍干净时才生成 `review-pass.json`。

## 兼容性说明

本版本不再兼容旧 severity aliases（严重级别别名），例如 `HIGH`、`MEDIUM`、`LOW`、`BLOCKER`、`BLOCKING` 和 `INFORMATIONAL`。调用方必须先更新 reviewer prompt（审查代理提示词）或集成脚本，让它们输出四个 canonical severity（规范严重级别）：`CRITICAL`、`IMPORTANT`、`WARNING`、`SUGGESTION`。

本仓库当前内置 reviewer prompt 已改为 canonical severity；发布前若存在外部自定义 reviewer，需要同步更新后再切换到本版本。
