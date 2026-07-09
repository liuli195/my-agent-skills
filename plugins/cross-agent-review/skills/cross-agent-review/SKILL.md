---
name: cross-agent-review
description: "运行跨代理审查。仅用于 Comet build completion（构建完成）、PR Flow local review（本地审查）或用户显式调用。"
---

# Cross-Agent Review

本 skill 运行独立 cross-agent review（跨代理审查），不推进 Comet phase（阶段），不运行构建或测试，不自动安装 Claude Agent SDK。

## 调用边界（强制）

ONLY ALLOWED:
- Comet build completion（构建完成）阶段：进入 verify（验证）前，生成 `review-report.md`（审查报告）；主 agent（主代理）确认无 CRITICAL（严重阻断）或 IMPORTANT（重要阻断）后，再写供 Agent Guard（代理守卫）build gate（构建门禁）使用的 pass marker（通过标记）。
- PR Flow（拉取请求流程）阶段已启用 local review（本地审查）。
- 用户显式调用 `cross-agent-review`（跨代理审查）。

STRICTLY FORBIDDEN:
- Comet verify（验证）阶段自动调用。
- 通用 code review（代码审查）阶段自动调用。

## 模式选择

本 Skill（技能）默认使用收敛模式。模式是主 agent（代理）准备输入和复审范围的策略，不新增 CLI（命令行接口）参数，不改变脚本调用方式。

`mode`（模式）只能是 `convergence`（收敛）或 `endless`（无尽）。

- Comet build completion（构建完成）或 PR Flow local review（本地审查）：使用 `convergence`（收敛）模式。首轮覆盖完整 review subject（审查对象）；修复 CRITICAL（严重阻断）或 IMPORTANT（重要阻断）findings（发现项）后重跑时，优先复核上一轮阻断问题、对应修复、变更路径和直接受影响上下文；只有证据显示风险外溢时再扩大范围。
- 用户显式调用 cross-agent-review（跨代理审查）且没有说明模式：使用 `convergence`（收敛）模式，按上面的首轮/复审规则处理。
- 用户明确要求“无尽模式”“每轮完整复查”“不要收窄范围”或等价表达：使用 `endless`（无尽）模式。每轮都覆盖完整 review subject（审查对象）和必要上下文，不按上一轮结果收窄；仍以没有 CRITICAL（严重阻断）或 IMPORTANT（重要阻断）findings（发现项）作为通过条件。

## 前置条件

- 当前 worktree 必须干净。
- 当前 `HEAD` 必须等于 `review-input.json`（审查输入文件）里的 `head_ref`。
- 当前 Python、默认 Claude SDK venv，或 `--sdk-python` 指定的 Python 必须能导入 `claude_agent_sdk`。
- reviewer（审查代理）使用 Claude Agent SDK（Claude 代理开发包）默认 tools（工具集）；本插件不配置 `tools`、`allowed_tools` 或 `disallowed_tools`。

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

主 agent（主代理）读完 `review-report.md`（审查报告）并确认可以通过后，再显式写入 guard-defined evidence（守卫定义证据）：

```bash
python scripts/cross_agent_review.py mark-pass \
  --input-file .local/cross-agent-review/<change>/<head_ref_short>/prepared-inputs/review-input.json
```

## 输入文件准备

`prepared-inputs`（预备输入目录）只包含一个 regular file（常规文件）：`review-input.json`（审查输入文件）。

路径固定为：

```text
.local/cross-agent-review/<change>/<head_ref_short>/prepared-inputs/review-input.json
```

`<head_ref_short>`（短头引用）等于 `head_ref`（头引用）的前 12 个字符。

不要在 `.local/` 下创建独立的输入根目录。

`review-input.json`（审查输入文件）字段固定为：

- `change`
- `mode`
- `base_ref`
- `head_ref`
- `spec_file`
- `design_file`
- `plan_file`

review（审查）范围由 `base_ref`（基准引用）和 `head_ref`（当前提交引用）控制；以下命令中的 `<base-ref>` 和 `<head-ref>` 必须分别来自这两个字段。

review subject（审查对象）命令包括：

```bash
git diff <base-ref>...<head-ref>
git log <base-ref>..<head-ref> --oneline
git diff --name-status --find-renames --find-copies-harder <base-ref>...<head-ref>
git diff <base-ref>...<head-ref> -- <path>
```

Reviewer prompt（审查代理提示词）引用 `review-input.json`（审查输入文件），不内联大 diff（差异）内容；reviewer（审查代理）按需读取相关片段，不能整读大 diff（差异）。
Reviewer prompt（审查代理提示词）会内联三条短命令：`git diff <base-ref>...<head-ref>`、`git log <base-ref>..<head-ref> --oneline` 和 `git diff --name-status --find-renames --find-copies-harder <base-ref>...<head-ref>`。

Comet build completion（构建完成）调用时，`base_ref` 应优先使用 implementation baseline（实施基准，例如 plan 文件头的 `base-ref`），避免把已完成的历史 change（变更）卷入本次 review（审查）diff（差异）。只有在没有实施基准时，才回退到 change init baseline（变更初始化基准）。

## Reviewer（审查代理）角色

默认 reviewer（审查代理）角色只有：

- `spec-alignment`
- `implementation-correctness`

## 输出文件

默认输出只有：

- `review-report.md`（审查报告）

`mark-pass`（标记通过）输出：

- `.local/guard/evidence/<profile_id>/cross_agent_review_pass/<change>/<head_ref_short>/pass.json`

只有使用 `--debug`（排障开关）时才写入 debug（排障）输出：

- `debug/review-input.json`
- `debug/prompts/<role>.txt`
- `debug/raw/<role>.txt`

## Timeout（超时）

插件内部保留 480 秒单 reviewer（审查代理）和 540 秒 SDK dispatch（开发包派发）timeout（超时），用于保证审查不会无限等待。

“不要手动添加 timeout/watchdog（超时/看门等待）”指主 agent（主代理）调用插件时不能在外层再包一层计时器，尤其不能设置短于插件内部 540 秒的外层 timeout（超时）。

## Reviewer 输出契约

Reviewer（审查代理）必须只返回一个轻量 Markdown（标记文本）结果，不要返回 JSON（结构化数据）或解释性前后缀。

格式固定为：

```markdown
# Review Result: <role>

## Findings
- Severity: CRITICAL|IMPORTANT|WARNING|SUGGESTION
  Location: path-or-component
  Summary: one-line issue summary
  Evidence: specific evidence from the supplied inputs
  Recommendation: concrete next action
```

只允许以下 severity（严重级别）值：

- `CRITICAL`（严重阻断）：可能导致数据丢失、安全暴露、必需流程中断，或 reviewer/tool（审查代理/工具）失败。
- `IMPORTANT`（重要阻断）：明确回归、缺少必需场景，或正常使用中很可能触发的边界错误。
- `WARNING`（警告）：有合理风险或覆盖缺口，但影响有限或不确定。
- `SUGGESTION`（建议）：可维护性或清晰度改进，不应阻断通过。

不要使用 severity aliases（严重级别别名），例如 `high`、`medium`、`low`、`minor` 或 `info`。
缺少 `Severity:` 的 finding（发现项）属于无效 reviewer 输出，主 agent（主代理）应按阻断处理或要求重新审查。

如果没有问题，`## Findings` 下写：

```markdown
No findings.
```

脚本只做文本聚合，不解析 finding（发现项）、不去重、不判断是否通过。主 agent（主代理）读取 `review-report.md` 后判断是否还有 CRITICAL（严重阻断）或 IMPORTANT（重要阻断），并在通过后运行 `mark-pass`（标记通过）。`mark-pass` 只写 Guard（守卫）默认 evidence（证据）目录，不读取或解析 reviewer（审查代理）正文。

## 兼容性说明

本版本不再要求 reviewer（审查代理）返回 JSON（结构化数据）findings（发现项）数组。调用方或外部自定义 reviewer（审查代理）需要改为上述 Markdown（标记文本）格式。
