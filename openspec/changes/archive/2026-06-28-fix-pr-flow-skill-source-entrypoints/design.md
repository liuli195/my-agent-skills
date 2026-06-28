## 根因

`pr-flow` 总入口把命令写成 `python scripts/pr_flow.py diagnose --project .`，但源码仓库实际脚本位于 `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`。

## 修复方案

只改总入口命令说明，明确源码仓库运行命令。不新增 wrapper（包装脚本），避免多一层维护入口。

## 验证

增加文本测试，检查总入口包含真实源码路径，并且不再包含无效的 `python scripts/pr_flow.py diagnose --project .`。
