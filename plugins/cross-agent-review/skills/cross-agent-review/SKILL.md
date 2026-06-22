---
name: cross-agent-review
description: "运行跨代理审查。Use when 需要在提交后的 clean commit 上运行 Claude Agent SDK reviewer，并生成 review report 和 review-pass.json。"
---

# Cross-Agent Review

本 skill 运行独立 cross-agent review（跨代理审查），不推进 Comet phase（阶段），不运行构建或测试，不自动安装 Claude Agent SDK。

## 前置条件

- 当前 worktree 必须干净。
- 当前 `HEAD` 必须等于传入的 `--head-ref`。
- 调用方已运行测试，并提供测试结果文件。
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
  --tasks-file <path> \
  --tests-file <path>
```

## 输入文件准备

`--diff-file` 和 `--tests-file` 等运行前生成的输入文件，必须放在同一次 review 的 run 目录下：

```text
.local/cross-agent-review/<change>/<head_ref>/prepared-inputs/
```

随后把这些文件路径显式传给命令参数。不要在 `.local/` 下创建独立的输入根目录；review 运行后会把最终输入快照复制到同一 run 目录的 `inputs/`。

输出默认写入 `.local/cross-agent-review/<change>/<head_ref>/`。运行时会先把输入文件快照复制到输出目录下的 `inputs/`：

- `inputs/diff.patch`
- `inputs/spec.md`
- `inputs/design.md`
- `inputs/tasks.md`
- `inputs/tests.txt`

只有没有 CRITICAL/IMPORTANT findings（发现项），且 worktree 仍干净时才生成 `review-pass.json`。
