---
name: cross-agent-review
description: "运行跨代理审查。仅用于 Comet build completion（构建完成）、PR Flow local review（本地审查）或用户显式调用。"
---

# Cross-Agent Review（跨代理审查）

本 Skill（技能）运行独立审查，不推进 Comet phase（双星阶段），不运行构建或测试，不自动安装 Claude Agent SDK（Claude 代理开发包）。

## 调用边界（强制）

ONLY ALLOWED:

- Comet build completion（双星构建完成）阶段进入 verify（验证）前。
- PR Flow（拉取请求流程）启用 local review（本地审查）时。
- 用户显式调用 cross-agent-review（跨代理审查）时。

STRICTLY FORBIDDEN:

- Comet verify（双星验证）阶段自动调用。
- 通用 code review（代码审查）阶段自动调用。

## 前置条件

- 当前 worktree（工作区）干净，当前 `HEAD`（提交头）等于输入中的 `head_ref`（头引用）。
- 当前 Python（脚本运行环境）、默认 Claude SDK venv（Claude 开发包虚拟环境），或 `--sdk-python` 指定的 Python（脚本运行环境）可以导入 `claude_agent_sdk`。
- 主 agent（主代理）直接等待脚本返回，不在外层增加短于 540 秒的 timeout/watchdog（超时/看门等待）。插件内部上限为单 reviewer（审查代理）480 秒、整体 SDK dispatch（开发包派发）540 秒。

## 命令

首次或重新执行真实审查：

```bash
python scripts/cross_agent_review.py run \
  --input-file .local/cross-agent-review/<change>/<head_ref_short>/prepared-inputs/review-input.json
```

只重试 `failed`（失败）或 `timed_out`（超时）的角色：

```bash
python scripts/cross_agent_review.py retry \
  --input-file .local/cross-agent-review/<change>/<head_ref_short>/prepared-inputs/review-input.json
```

只验证声明式机械变化并复用上一轮完成结果：

```bash
python scripts/cross_agent_review.py revalidate \
  --input-file .local/cross-agent-review/<change>/<head_ref_short>/prepared-inputs/review-input.json \
  --previous-state .local/cross-agent-review/<change>/<previous_head_ref_short>/review-state.json
```

`run/retry/revalidate`（运行/重试/重新校验）只生成 `review-report.md`（审查报告）和 `review-state.json`（审查状态）。主 agent（主代理）读取两者并作出语义结论；外部 workflow（工作流）需要证据时，调用该 workflow（工作流）自己声明的通用证据入口。

本 Skill（技能）不知道 Guard Profile（守卫画像）、artifact id（产物编号）、证据路径或 evidence schema（证据结构）。

## 输入文件

`prepared-inputs`（预备输入目录）只包含 `review-input.json`（审查输入文件），固定路径为：

```text
.local/cross-agent-review/<change>/<head_ref_short>/prepared-inputs/review-input.json
```

`<head_ref_short>`（短头引用）等于 `head_ref`（头引用）的前 12 个字符。

完整示例：

```json
{
  "change": "demo",
  "mode": "convergence",
  "base_ref": "origin/main",
  "head_ref": "0123456789abcdef0123456789abcdef01234567",
  "spec_file": "openspec/changes/demo/specs/capability/spec.md",
  "design_file": "openspec/changes/demo/design.md",
  "plan_file": "docs/superpowers/plans/demo.md",
  "summary_only": [
    {
      "path": "docs/process.md",
      "reason": "过程文档仅供按需核对"
    }
  ],
  "revalidation_policy": [
    {
      "path": "docs/checklist.md",
      "validator": "checkbox-only"
    },
    {
      "path": "manifest.yaml",
      "validator": "mapping-fields-only",
      "format": "yaml",
      "fields": [
        "status",
        "evidence"
      ]
    }
  ]
}
```

`mode`（模式）只能是 `convergence`（收敛）或 `endless`（无尽）。review（审查）范围由 `base_ref`（基准引用）和 `head_ref`（当前提交引用）控制。

- `summary_only`（仅摘要）逐项使用精确项目相对路径和非空 `reason`（理由）；它只降低主要输入噪音，不禁止 reviewer（审查代理）按需读取原文。
- `checkbox-only`（仅复选框）只允许 Markdown task checkbox（标记任务复选框）状态变化。
- `mapping-fields-only`（仅映射字段）只允许 JSON/YAML（数据/配置）顶层映射中列出的字段变化。
- 未分类文件默认进入 `full_review`（完整审查），不能按扩展名、目录或大小排除。

出现未声明文件、重叠策略、解析失败、规格或设计变化、重命名、复制、脏工作区或哈希不匹配时，`revalidate`（重新校验）拒绝复用；更新当前输入后，改用 `run`（运行）执行真实审查。不得把失败降级成局部复用或伪造结果。

审查范围可用以下命令核对：

```bash
git diff --name-status --find-renames --find-copies-harder <base-ref>...<head-ref>
git diff <base-ref>...<head-ref> -- <path>
```

## Reviewer（审查代理）与输出

固定角色只有：

- `spec-alignment`（规格对齐）
- `implementation-correctness`（实施正确性）

每个角色返回轻量 Markdown（标记文本）：

```markdown
# Review Result: <role>

## Findings
- Severity: CRITICAL|IMPORTANT|WARNING|SUGGESTION
  Location: path-or-component
  Summary: one-line issue summary
  Evidence: specific evidence from the supplied inputs
  Recommendation: concrete next action
```

没有问题时在 `## Findings` 下写 `No findings.`。只允许 `CRITICAL`（严重阻断）、`IMPORTANT`（重要阻断）、`WARNING`（警告）、`SUGGESTION`（建议），不要使用 severity aliases（严重级别别名）；缺少 `Severity:` 的 finding（发现项）按阻断处理或要求重新审查。

脚本只聚合文本并保存角色状态，不解析 finding（发现项）、不去重、不判断是否通过。主 agent（主代理）负责语义判断。

默认输出：

- `review-report.md`（审查报告）
- `review-state.json`（审查状态）

只有 `run/retry`（运行/重试）使用 `--debug`（排障开关）时才增加：

- `debug/review-input.json`（排障输入）
- `debug/prompts/<role>.txt`（角色提示词）
- `debug/raw/<role>.txt`（角色原始输出）
