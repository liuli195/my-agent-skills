## Design

本次 tweak（小改）只调整文字契约。模式选择由调用方和 reviewer prompt（审查提示词）表达，不进入 Python（脚本）参数，也不改变输出产物。

默认模式为收敛模式：

- 首轮覆盖完整 review subject（审查对象）。
- 修复 CRITICAL（严重阻断）或 IMPORTANT（重要阻断）findings（发现项）后，复审优先聚焦上一轮阻断问题、对应修复、变更路径和直接受影响上下文。
- 只有证据显示相关风险超出当前范围时，扩大到完整 review subject（审查对象）。

显式无尽模式只在用户或调用方明确要求时启用：

- 每轮都覆盖完整 review subject（审查对象）和必要上下文。
- 不按上一轮 findings（发现项）收窄范围。

## Boundaries

- 不修改 `scripts/cross_agent_review.py`。
- 不新增 CLI（命令行接口）参数。
- 不改变 `.local/cross-agent-review/<change>/<head_ref>/` 输出契约。
- 不新增测试，仅运行现有文档、规格和快速验证入口。
