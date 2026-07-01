---
comet_change: simplify-cross-agent-review-contract
role: technical-design
canonical_spec: openspec
archived-with: 2026-06-26-simplify-cross-agent-review-contract
status: final
---

# Simplify Cross-Agent Review Contract Design

## Context

`cross-agent-review`（跨代理审查）当前实现仍保留多层旧契约：

- CLI（命令行接口）要求分别传入 `spec_file`、`design_file` 和 `tasks_file`。
- 脚本默认复制输入快照并生成 `inputs/manifest.json`。
- 默认派发四个 reviewer agent（审查代理）。
- 默认输出 `review-results.json`、`prompts/<role>.txt` 和 `raw/<role>.txt`。
- `convergence mode`（收敛模式）主要停留在提示词说明，没有通过 `base_ref`（基准引用）和 `head_ref`（当前提交引用）形成硬范围。

这让一次 review（审查）的输入、提示词和输出都偏重，也让 rerun（重新审查）不容易真正收敛。

## Confirmed Design

本次采用一次性收敛契约和实现的方案，不保留旧 CLI（命令行接口）兼容层。

原因：

- 旧启动路径正是复杂度来源，兼容层会继续保留 `tasks_file`、快照和默认调试输出这些旧行为。
- 角色、提示词和输出互相耦合，局部加开关会让默认路径继续不符合新契约。
- 本仓库内测试可统一更新，调用方也能通过一个输入文件完成迁移。

## Input Contract

调用方必须先写入：

```text
.local/cross-agent-review/<change>/<head_ref_short>/prepared-inputs/review-input.json
```

脚本只接受：

```powershell
python scripts/cross_agent_review.py run --input-file .local/cross-agent-review/<change>/<head_ref_short>/prepared-inputs/review-input.json
```

排障时显式增加 `--debug`（排障开关）：

```powershell
python scripts/cross_agent_review.py run --input-file .local/cross-agent-review/<change>/<head_ref_short>/prepared-inputs/review-input.json --debug
```

`review-input.json`（审查输入文件）包含：

```json
{
  "change": "add-build-and-verify-init-skill",
  "mode": "convergence",
  "base_ref": "d6a1ca3c11e7648678a68186fe76f4ada92a1342",
  "head_ref": "8a2ccd24234d...",
  "spec_file": "openspec/changes/<change>/specs/<capability>/spec.md",
  "design_file": "docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md",
  "plan_file": "docs/superpowers/plans/YYYY-MM-DD-<topic>.md"
}
```

`plan_file`（计划文件）替代 `tasks_file`（任务文件），指向 Superpowers plan（超级能力计划）。

`prepared-inputs`（预备输入目录）作为输入目录只允许一个普通文件：`review-input.json`。旧的 `spec.md`、`design.md`、`tasks.md`、`plan.md` 或 `manifest.json` 不再写入该目录。

## Validation Flow

脚本启动后按顺序校验：

1. `review-input.json` 位于 `prepared-inputs`（预备输入目录）下。
2. `prepared-inputs`（预备输入目录）只包含 `review-input.json`。
3. 必填字段完整。
4. `mode` 只能是 `convergence`（收敛）或 `endless`（无尽）。
5. `spec_file`、`design_file` 和 `plan_file` 存在。
6. 当前 worktree（工作区）干净，但允许本次 `review-input.json` 和本次输出目录作为 runtime artifacts（运行产物）。这份 allowlist（允许清单）同时用于启动、派发前和生成 `review-pass.json` 前的所有 clean worktree（干净工作区）检查。
7. `head_ref` 等于当前 `HEAD`（当前提交）。
8. `base_ref` 可被 Git（版本控制）解析。

通过后，review subject（审查对象）始终由 `base_ref...head_ref` 定义。

## Mode Semantics

`convergence`（收敛）和 `endless`（无尽）都保留，但都通过输入文件里的 `base_ref` 和 `head_ref` 生效。

`convergence`（收敛）：

- 首轮：`base_ref` 是 implementation baseline（实施基准），`head_ref` 是当前已提交 `HEAD`。
- 修复后 rerun（重新审查）：`base_ref` 是上一轮失败 review（审查）的 `head_ref`，`head_ref` 是修复后的当前 `HEAD`。
- reviewer agent（审查代理）只审查 `base_ref...head_ref`，除非代码证据显示需要扩大上下文。

`endless`（无尽）：

- 每轮都保持 `base_ref` 为完整 implementation baseline（实施基准）或调用方提供的完整 baseline（基准）。
- `head_ref` 是当前已提交 `HEAD`。
- 不因为上一轮 finding（发现项）已修复而收窄范围。

## Reviewer Dispatch

默认 reviewer agent（审查代理）只保留两个：

- `spec-alignment`（规格一致性）：检查实现是否满足 `spec_file`、`design_file` 和 `plan_file` 声明的要求。
- `implementation-correctness`（实现正确性）：检查当前 diff（差异）里的实现错误、兼容性错误和状态/数据流问题。

删除：

- `tests-and-edge-cases`（测试和边界）
- `risk-review`（风险审查）
- `--disable-risk-review`（关闭风险审查）兼容行为

`cross-agent-review`（跨代理审查）仍不运行测试；测试和构建继续由 Comet verify（彗星验证）负责。

## Prompt Design

提示词只保留稳定规则和输入文件引用：

```text
Role: <role>

Read: <prepared-inputs/review-input.json>

Use read-only inspection. Do not edit files.
Review only base_ref...head_ref from the input file.
Use spec_file, design_file, and plan_file as requirements context.

Focus:
<role focus>

Return one JSON object:
role, status, findings[]
finding: severity, location, summary, evidence, recommendation
severity: CRITICAL | IMPORTANT | WARNING | SUGGESTION
If no issues: findings=[]
```

提示词不得内联完整 diff（差异）、上下文文件正文、changed files（变更文件）清单、manifest（清单）或长命令块。

## Output Contract

默认输出目录仍为：

```text
.local/cross-agent-review/<change>/<head_ref_short>/
```

默认只写：

- `review-report.md`（审查报告）
- `review-pass.json`（通过标记），仅在 blocking findings（阻塞发现）为 0 时写入

不再默认写：

- `review-results.json`
- `inputs/manifest.json`
- `inputs/spec.md`
- `inputs/design.md`
- `inputs/tasks.md`
- `prompts/<role>.txt`
- `raw/<role>.txt`

显式 debug mode（排障模式）才写：

- `debug/review-input.json`
- `debug/prompts/<role>.txt`
- `debug/raw/<role>.txt`

`review-pass.json`（通过标记）新增 `mode` 字段，用于记录本次 review（审查）使用的模式。

## Implementation Notes

实现上建议先重构数据模型，再替换行为：

1. 引入从 `--input-file` 加载的 `ReviewInput`（审查输入）或等价结构。
2. 将现有 `ReviewArgs`（审查参数）字段改为从输入文件派生。
3. 删除 `INPUT_SNAPSHOT_NAMES`（输入快照名称）和 `archive_input_snapshots`（归档输入快照）调用链。
4. 保留 Git（版本控制）命令构造能力，但只在脚本内部按需使用，不写 manifest（清单）。
5. 调整 `REVIEWER_ROLES`（审查代理角色）和 `ROLE_FOCUS`（角色重点）。
6. 调整 prompt template（提示词模板）变量，只传 role（角色）、input file path（输入文件路径）、role focus（角色重点）、severity rubric（严重级别规则）和 output schema（输出结构）。
7. 调整输出写入逻辑，默认不写结果 JSON（结构化结果）和排障文件。
8. 用 debug flag（排障开关）控制排障产物。
9. 搜索并更新仓库内所有旧 `spec_file` / `design_file` / `tasks_file` 调用方。

## Testing

测试按契约更新：

- missing input file（输入文件缺失）失败。
- missing required field（必填字段缺失）失败。
- missing referenced file（引用文件缺失）失败。
- invalid mode（非法模式）失败。
- invalid base ref（非法基准引用）失败。
- head mismatch（当前提交不匹配）失败。
- prepared-inputs（预备输入目录）出现额外普通文件时失败。
- runtime artifacts（运行产物）例外只允许当前输入文件和当前输出目录。
- 启动、派发前和生成 `review-pass.json`（通过标记）前复用同一 runtime artifacts（运行产物）允许清单。
- 默认 reviewer roles（审查代理角色）只有两个。
- 默认输出不包含 `review-results.json`、`inputs/manifest.json`、`prompts/` 或 `raw/`。
- debug mode（排障模式）输出 `debug/` 下的输入、提示词和原始响应。
- `review-pass.json`（通过标记）包含 `mode`，并覆盖 `convergence`（收敛）和 `endless`（无尽）。
- prompt（提示词）只引用 `review-input.json`，不内联大上下文。

## Risks

- 旧调用方会失败，需要同步改成 `--input-file`。
- 默认排障信息减少，排障时必须显式开启 debug mode（排障模式）。
- 移除两个 reviewer agent（审查代理）会减少审查维度，但这与“审查只负责规格和实现一致性，测试由验证阶段负责”的边界一致。
