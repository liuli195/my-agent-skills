---
name: my-spec-review
description: 审查 OpenSpec（开放规格）规格库内部的冲突、重复和过期项。当用户要求只审查 openspec/specs/ 时使用。
---

# my-spec-review

只审查 `openspec/specs/`，不得读取仓库其他文件。

执行前读取：

1. [公共规则](../my-spec/references/openspec-rules.md)
2. [规格审查流程](../my-spec/references/review.md)
3. [统一入口门禁](../my-spec/SKILL.md)

模板位于 `../my-spec/assets/`；所有确定性操作调用 `../my-spec/scripts/spec_ops.py`。
