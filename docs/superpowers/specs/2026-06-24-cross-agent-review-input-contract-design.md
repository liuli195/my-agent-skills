---
comet_change: refactor-cross-agent-review-input-contract
role: technical-design
canonical_spec: openspec
---

# Cross-Agent Review Input Contract Design

## Context

`cross-agent-review`（跨代理审查）用于对一个固定 `HEAD`（头提交）做只读、多角色审查，并产出结构化 review report（审查报告）和可选 `review-pass.json`（通过标记）。`Comet`（双星流程）、`PR Flow`（拉取请求流程）和用户手动调用只是上游调用方；插件核心契约不应理解这些流程的内部产物。

现有实现把 `diff.patch`（差异补丁）作为必需输入，并在 Python（脚本）里硬编码 `reviewer prompt`（审查提示词）。这会让审查范围退回“大文件输入”模式，也让提示词维护和脚本行为耦合。

## Design

核心输入改为 review subject（审查对象）：

```bash
python scripts/cross_agent_review.py run \
  --change <review-id> \
  --base-ref <fixed-point> \
  --head-ref <head-ref> \
  --spec-file <path> \
  --design-file <path> \
  --tasks-file <path>
```

`base_ref`（基线引用）由调用方明确提供，可以是 commit（提交）、branch（分支）、tag（标签）、`main` 或 `HEAD~5` 等 git ref（引用）。如果调用方没有明确 fixed point（固定点），技能说明要求先询问用户，不自行推断。

Python（脚本）在运行时生成 `inputs/manifest.json`（清单），其中 `review_subject`（审查对象）记录：

- `git diff <base_ref>...<head_ref>`
- `git log <base_ref>..<head_ref> --oneline`
- `git diff --name-status <base_ref>...<head_ref>`
- `git diff <base_ref>...<head_ref> -- <path>`
- `merge_base`（合并基点）
- `commits`（提交列表）
- `changed_files`（变更文件）

系统不再写入 `inputs/diff.patch`（差异补丁），也不把补丁文件传给 reviewer（审查者）。Reviewer（审查者）需要查看差异时，使用 `manifest.json`（清单）中的 path-scoped diff（按路径限定差异）命令。

## Prompt Template

新增独立模板文件，例如：

```text
plugins/cross-agent-review/skills/cross-agent-review/assets/templates/reviewer-prompt.md
```

模板用于维护 `reviewer prompt`（审查提示词）正文，方便修改和复用。Python（脚本）仍是调用方和渲染入口，负责：

- 读取模板文件。
- 生成模板变量。
- 填充 role（角色）、schema（输出结构）、severity rubric（严重级别规则）、role focus（角色重点）、manifest path（清单路径）、commands（命令）、changed files（变更文件）和 context files（上下文文件）。
- 写入 `prompts/<role>.txt` 供排障复现。

模板渲染只做简单占位符替换，不引入新依赖。

## Data Flow

1. 调用方运行 Python（脚本）并传入 `base_ref`（基线引用）、`head_ref`（头引用）和上下文文件。
2. 脚本校验 worktree（工作区）干净，且当前 `HEAD`（头提交）等于 `head_ref`（头引用）。
3. 脚本复制 `spec/design/tasks`（规格/设计/任务）到 `inputs/`。
4. 脚本运行只读 git commands（命令）生成 `manifest.json`（清单）。
5. 脚本读取模板并生成每个 role（角色）的 prompt（提示词）。
6. Reviewer（审查者）按需运行 path-scoped diff（按路径限定差异）命令和读取上下文文件。
7. 脚本汇总 findings（发现项），生成 report（报告）和可选 pass marker（通过标记）。

## Timeout

超时仍由插件内部脚本管理：

- 单个 reviewer timeout（审查者超时）：480 秒。
- 整体 dispatch timeout（派发超时）：540 秒。

主 agent（代理）调用插件时不得再包小于 540 秒的外层 timeout（超时）或等价 watchdog（看门等待）。外层短超时会绕过插件的结构化 CRITICAL finding（严重发现项）输出。

## Testing

测试按 TDD（测试驱动开发）推进：

- CLI（命令行接口）不再要求 `--diff-file`（差异文件）。
- 输出目录不包含 `inputs/diff.patch`（差异补丁）。
- `manifest.json`（清单）包含三点 diff（三点差异）、commit list（提交列表）、changed files（变更文件）和 path-scoped diff（按路径限定差异）命令模板。
- changed files（变更文件）解析覆盖 added（新增）、modified（修改）、deleted（删除）、renamed（重命名）和带空格路径。
- `reviewer prompt`（审查提示词）来自独立模板文件，且不内联 diff output（差异输出）或上下文正文。
- 内部 timeout（超时）常量和调用说明保持一致。

## Implementation Divergence

实施过程中，`changed files command`（变更文件命令）从设计阶段的基础命令：

```bash
git diff --name-status <base_ref>...<head_ref>
```

收紧为：

```bash
git diff --name-status --find-renames --find-copies-harder <base_ref>...<head_ref>
```

原因是质量审查发现 Git（版本控制）默认不会稳定识别普通 copy（复制）场景，复制文件可能被记录为 added（新增）。加入 rename/copy（重命名/复制）检测后，`manifest.json`（清单）中的 `changed_files`（变更文件）可以稳定表达 `renamed`（已重命名）和 `copied`（已复制），并保留 `previous_path`（原路径）。该收紧已同步到 delta spec（增量规格）、实现、技能说明和测试。
