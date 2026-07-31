# 02 配置变化时选择全部检查

**Status:** ready-for-agent  
**Prerequisites:** none  
**Source:** GitHub Issue #239

## 用户结果

用户修改 `.build-and-verify/config.json`（配置文件）后运行 fast verify（快速验证），全部当前验证检查都会进入选择范围，并能看到一次明确原因说明。

## 验收标准

- 配置文件是唯一 changed file（变更文件）时，选择全部当前 `verify.checks`（验证检查项）。
- 输出只包含一条整体选择原因。
- 配置结构错误在任何检查调度前失败。
- 旧配置生成的缓存不能命中；当前配置已生成的缓存可以复用。
- 配置变化扩大选择范围但不强制重跑缓存命中的检查。
- 普通源码变化继续按现有 `paths`（受影响路径）选择检查。
- canonical runtime（规范运行时）与仓库 runtime snapshot（运行时快照）一致。

## 红灯与验证

1. 使用现有 fake runner（假执行器）增加失败检查：唯一变更为配置文件时，全部当前检查应被选择。
2. 覆盖整体原因输出、无效配置、当前配置缓存复用和普通路径选择。
3. 用同一组检查转绿。
4. 通过 Build and Verify（构建与验证）运行定向检查，并从仓库 runtime（运行时）的 fast verify（快速验证）命令执行最小真实冒烟。
