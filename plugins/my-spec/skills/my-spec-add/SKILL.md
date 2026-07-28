---
name: my-spec-add
description: 从用户指定文档新增或更新 OpenSpec（开放规格）。当用户要求把一份明确指定的文档转换为规格时使用。
---

# my-spec-add

只处理用户指定文档，不扫描仓库其他内容。

执行前读取：

1. [公共规则](../my-spec/references/openspec-rules.md)
2. [新增文档流程](../my-spec/references/add-document.md)
3. [统一入口门禁](../my-spec/SKILL.md)

模板位于 `../my-spec/assets/`；所有确定性操作调用 `../my-spec/scripts/spec_ops.py`。
