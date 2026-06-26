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

## 模式选择

本 Skill（技能）默认使用收敛模式。模式是主 agent（代理）准备输入和复审范围的策略，不新增 CLI（命令行接口）参数，不改变脚本调用方式。

- Comet build completion（构建完成）或 PR Flow local review（本地审查）：使用收敛模式。首轮覆盖完整 review subject（审查对象）；修复 CRITICAL（严重阻断）或 IMPORTANT（重要阻断）findings（发现项）后重跑时，优先复核上一轮阻断问题、对应修复、变更路径和直接受影响上下文；只有证据显示风险外溢时再扩大范围。
- 用户显式调用 cross-agent-review（跨代理审查）且没有说明模式：使用收敛模式，按上面的首轮/复审规则处理。
- 用户明确要求“无尽模式”“每轮完整复查”“不要收窄范围”或等价表达：使用无尽模式。每轮都覆盖完整 review subject（审查对象）和必要上下文，不按上一轮结果收窄；仍以没有 CRITICAL（严重阻断）或 IMPORTANT（重要阻断）findings（发现项）作为通过条件。

## 前置条件

- 当前 worktree 必须干净。
- 当前 `HEAD` 必须等于 `review-input.json`（审查输入文件）里的 `head_ref`。
- 当前 Python、默认 Claude SDK venv，或 `--sdk-python` 指定的 Python 必须能导入 `claude_agent_sdk`。

## 命令

```bash
python scripts/cross_agent_review.py run \
  --input-file .local/cross-agent-review/<change>/<head_ref_short>/prepared-inputs/review-input.json
```

排障时显式开启 `--debug`（排障开关）：

```bash
python scripts/cross_agent_review.py run \
  --input-file .local/cross-agent-review/<change>/<head_ref_short>/prepared-inputs/review-input.json \
  --debug
```

## 输入文件准备

`prepared-inputs`（预备输入目录）只包含一个 regular file（常规文件）：`review-input.json`（审查输入文件）。

路径固定为：

```text
.local/cross-agent-review/<change>/<head_ref_short>/prepared-inputs/review-input.json
```

不要在 `.local/` 下创建独立的输入根目录。

`review-input.json`（审查输入文件）字段固定为：

- `change`
- `mode`
- `base_ref`
- `head_ref`
- `spec_file`
- `design_file`
- `plan_file`

review subject（审查对象）命令包括：

```bash
git diff <base-ref>...<head-ref>
git log <base-ref>..<head-ref> --oneline
git diff --name-status --find-renames --find-copies-harder <base-ref>...<head-ref>
git diff <base-ref>...<head-ref> -- <path>
```

Reviewer prompt（审查代理提示词）引用 `review-input.json`（审查输入文件），不内联大 diff（差异）内容；reviewer（审查代理）按需读取相关片段，不能整读大 diff（差异）。

Comet build completion（构建完成）调用时，`base_ref` 应优先使用 implementation baseline（实施基准，例如 plan 文件头的 `base-ref`），避免把已完成的历史 change（变更）卷入本次 review（审查）diff（差异）。只有在没有实施基准时，才回退到 change init baseline（变更初始化基准）。

## Reviewer（审查代理）角色

默认 reviewer（审查代理）角色只有：

- `spec-alignment`
- `implementation-correctness`

## 输出文件

默认输出只有：

- `review-report.md`（审查报告）
- `review-pass.json`（通过标记），仅在通过时生成

只有使用 `--debug`（排障开关）时才写入 debug（排障）输出：

- `debug/review-input.json`
- `debug/prompts/<role>.txt`
- `debug/raw/<role>.txt`

## Timeout（超时）

插件内部管理 480 秒单 reviewer（审查代理）和 540 秒 SDK dispatch（开发包派发）timeout（超时）。主 agent（主代理）调用时不要在外层包装短于 540 秒的 timeout/watchdog（超时/看门等待）。

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
