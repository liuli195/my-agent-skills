## Why

原生 Git（版本管理）删除 Orca（工作区管理器）托管的隔离工作树时，可能因 Orca（工作区管理器）终端占用而只注销 Git（版本管理）登记、遗留无法删除的目录。PR Flow（拉取请求流程）需要优先让 Orca（工作区管理器）协调其已登记的工作树，避免双重删除和部分完成状态。

## What Changes

- 删除非主工作树前，探测目标绝对路径是否由 Orca（工作区管理器）登记。
- 已登记时，使用非强制 `orca worktree rm`（Orca 工作树删除）删除，不调用原生 Git（版本管理）删除。
- 未登记、Orca（工作区管理器）不可用或查询失败时，保留现有非强制 Git（版本管理）删除行为。
- Orca（工作区管理器）已登记但删除失败时，停止并保留 Orca（工作区管理器）诊断，不回退 Git（版本管理）删除。
- 为选择、回退和失败边界补充回归测试与技能说明。

## Capabilities

### New Capabilities

- 无。

### Modified Capabilities

- `pr-flow-plugin`：工作树删除按 Orca（工作区管理器）登记状态选择安全删除器，并保留明确的停止和回退边界。

## Impact

- `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py` 中的工作树删除路径。
- `plugins/pr-flow/skills/pr-flow-cleanup/SKILL.md`、`plugins/pr-flow/skills/pr-flow-complete/SKILL.md` 和 `plugins/pr-flow/skills/pr-flow-hotfix/SKILL.md` 中的删除工作树说明。
- `tests/test_pr_flow_cli.py` 中的 PR Flow（拉取请求流程）回归测试。
- 不新增 Python（编程语言）依赖、不改变 Git（版本管理）主工作树保护、不使用强制删除或修改 Orca（工作区管理器）配置。
