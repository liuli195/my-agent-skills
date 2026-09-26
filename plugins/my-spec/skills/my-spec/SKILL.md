---
name: my-spec
description: 统一管理 MySpec（自有规格）。当用户调用统一入口，或请求同时涉及新增、内部审查和仓库审计而尚未选择专用入口时使用。
---

# my-spec

维护 `myspec/specs/` 这一唯一事实源。结构关键字使用英文，正文语言不限。

## 入口

- `my-spec-add`：读取 [references/add-document.md](references/add-document.md)，根据 Agent（代理）为当前请求选取的相关证据新增或更新规格，不执行全仓库审计。
- `my-spec-review`：读取 [references/review.md](references/review.md)，只审查规格库内部。
- `my-spec-audit`：读取 [references/audit.md](references/audit.md)，审计 Git（版本管理）可见的整个仓库；规格库不存在时按空库初始化。

用户未指定入口时，根据请求范围选择且只执行一个入口；范围不明确时先询问。

修改前同时读取 [references/myspec-rules.md](references/myspec-rules.md)。创建内容时复用 `assets/` 模板。所有确定性状态、校验、预览、完整差异和应用都调用裸 `myspec ...` CLI（命令行程序）；不得解析包内脚本路径。

## 不可跳过的门禁

1. 获取当前目标工作树的 `.local/spec-work/lock`；同一目标工作树已有锁时停止，不按时间自动清理。发布模式下不同目标工作树的锁互不阻塞；开发模式继续使用机器级单一开发源码绑定，但源码工作树只提供实现，不决定规格数据目标。
2. 调用 `myspec state-init`，在 `.local/spec-work/current/` 保存当前命令、输入与主规格指纹、实现身份、目标工作树、完整 `conflicts`、`currentConflict` 和本次 `decisions`。
3. 分析完成后必须在首次展示前调用 `myspec state-set-conflicts` 一次性保存全部冲突、删除和低可信候选；只保存数量或第一项无效。
4. `WAITING_DECISION` 期间只调用 `myspec state-current`、`myspec state-decide` 和 `myspec state-status` 读取已保存清单，禁止重新扫描获取下一项；一次只展示一条，禁止批量接受。
5. 未决项全部处理后，校验 Delta（增量规格），生成并校验预览。
6. 展示完整、不截断的文件级差异并等待最终确认；确认前不得改动主规格。
7. 应用前重算主规格和输入指纹；变化时停止并重新分析。规格根、Delta 根、预览根和目标工作树必须与本次运行首次预览时一致；缺失预览或实现身份变化时不得直接替换。
8. 原子替换后再次校验；失败时恢复原目录。成功后才清理本次工作区和锁。

不保存跨运行的忽略、暂缓决定或长期审计报告。不要使用 Git（版本管理）回滚，也不要触碰 `myspec/specs/` 之外的用户内容。
