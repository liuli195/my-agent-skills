# 01 展开通配符缓存输入

**Status:** ready-for-agent  
**Prerequisites:** none  
**Source:** GitHub Issue #238

## 用户结果

用户可在 `inputs`（缓存输入）中声明通配符；匹配文件新增、删除或修改后，fast verify（快速验证）不会错误命中旧缓存。

## 验收标准

- `requirements*.txt` 展开并哈希全部匹配的 Git 可见文件。
- 通配符只匹配文件，结果稳定排序，并保留模式和匹配集合的缓存语义。
- 匹配文件内容变化、新增或删除都会改变缓存结果。
- 空匹配作为合法 Future Input（未来输入）保留；初始化和审查提示但验证运行时静默。
- 字面缺失路径与 Future Input（未来输入）的提示明确区分。
- 正斜杠和反斜杠模式结果一致。
- 绝对路径、`..` 越界和项目外部匹配继续被拒绝。
- 字面单文件保留忽略文件例外，通配符文件集合遵循 Git 可见边界。
- canonical runtime（规范运行时）与仓库 runtime snapshot（运行时快照）一致。

## 红灯与验证

1. 在现有 runner integration seam（运行器集成接缝）增加失败检查，覆盖匹配文件内容变化、新增、删除和空匹配。
2. 增加 Git 忽略、Windows（Windows 系统）路径分隔符和越界回归检查。
3. 增加初始化与审查文档契约检查，证明两类缺失提示不同。
4. 用同一组检查转绿。
5. 通过 Build and Verify（构建与验证）运行定向检查，并从仓库 runtime（运行时）的 verify（验证）命令执行最小真实冒烟。
