---
name: my-spec
description: 统一管理 OpenSpec（开放规格）。当用户调用统一入口，或请求同时涉及新增、内部审查和仓库审计而尚未选择专用入口时使用。
---

# my-spec

维护 `openspec/specs/` 这一唯一事实源。结构关键字使用英文，正文语言不限。

## 入口

- `my-spec-add`：读取 [references/add-document.md](references/add-document.md)，只处理用户指定文档。
- `my-spec-review`：读取 [references/review.md](references/review.md)，只审查规格库内部。
- `my-spec-audit`：读取 [references/audit.md](references/audit.md)，审计 Git（版本管理）可见的整个仓库；规格库不存在时按空库初始化。

用户未指定入口时，根据请求范围选择且只执行一个入口；范围不明确时先询问。

修改前同时读取 [references/openspec-rules.md](references/openspec-rules.md)。创建内容时复用 `assets/` 模板。所有确定性校验、预览、完整差异和应用都调用 `scripts/spec_ops.py`。

## 不可跳过的门禁

1. 获取仓库级 `.local/spec-work/lock`；已有锁时停止，不按时间自动清理。
2. 在 `.local/spec-work/current/` 保存当前命令、输入与主规格指纹、冲突游标和本次决定。
3. 冲突、删除和低可信候选一次只展示一条，禁止批量接受。
4. 未决项全部处理后，校验 Delta（增量规格），生成并校验预览。
5. 展示完整、不截断的文件级差异并等待最终确认；确认前不得改动主规格。
6. 应用前重算主规格指纹；变化时停止并重新分析。
7. 原子替换后再次校验；失败时恢复原目录。成功后才清理本次工作区和锁。

不保存跨运行的忽略、暂缓决定或长期审计报告。不要使用 Git（版本管理）回滚，也不要触碰 `openspec/specs/` 之外的用户内容。
