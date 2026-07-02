## Why

`cross-agent-review`（跨代理审查）当前把 `diff.patch`（差异补丁）作为核心输入之一，这容易把 review（审查）范围误解为“大文件输入”，也容易诱导 reviewer（审查者）整读大 `diff`（差异）。更稳定的契约应当是：由明确的 `fixed point`（固定点）和 `head_ref`（头引用）定义可复现的 git diff command（差异命令）。

现在需要把 `cross-agent-review`（跨代理审查）改成流程无关的 `review subject`（审查对象）契约：调用方提供 baseline（基线）和 head（头引用），插件生成 manifest（清单）里的可复现命令、commit list（提交列表）和 changed files（变更文件），reviewer（审查者）按路径范围读取。

## What Changes

- 移除 `diff.patch`（差异补丁）作为核心必需输入；核心输入改为 `base_ref`（基线引用）和 `head_ref`（头引用）。
- 在 `manifest`（清单）中记录 `git diff <base_ref>...<head_ref>`、`git log <base_ref>..<head_ref> --oneline`、`git diff --name-status <base_ref>...<head_ref>` 和 path-scoped diff（按路径限定差异）命令模板。
- 明确 `review agent`（审查代理）应从 `manifest`（清单）、commit list（提交列表）、changed files（变更文件）和上下文文件路径按需读取。
- 不再保存或传递 `diff.patch`（差异补丁）；如需查看差异，reviewer（审查者）通过 manifest（清单）里的 git commands（命令）按需读取。
- 将 `reviewer prompt`（审查提示词）模板从 Python 脚本中抽出到独立模板文件，方便修改和复用；调用方仍是 Python 脚本，脚本只负责读取模板并填充角色、命令、清单路径和上下文路径。
- 明确主 `agent`（代理）调用插件时不得再包装外部短 `timeout`（超时）；插件脚本内部保留 8 分钟单 `reviewer`（审查代理）超时和 9 分钟总派发超时。
- 补充测试，防止未来把大输入重新内联进提示词、重新把 `diff.patch`（差异补丁）作为核心输入，或在调用说明中引入外部短超时包装。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `cross-agent-review`: 输入契约和调用超时契约变为更严格的规格级行为。

## Impact

- `plugins/cross-agent-review/skills/cross-agent-review/SKILL.md`
- `plugins/cross-agent-review/skills/cross-agent-review/scripts/cross_agent_review.py`
- `tests/test_cross_agent_review_cli.py`
- `openspec/specs/cross-agent-review/spec.md`
