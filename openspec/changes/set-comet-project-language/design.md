# Design: 设置 Comet 项目语言

## 修复方案

在项目级 `.comet/config.yaml` 增加：

```yaml
language: zh-CN
```

当前 Comet（双星流程）运行时仅接受 `en` 和 `zh-CN`，初始化新变更时会把项目默认值写入该变更自己的 `.comet.yaml`。

## 边界

- 不修改 Comet（双星流程）运行时代码。
- 不回写已存在或已归档变更的语言。
- 不修改 `context_compression` 和 `auto_transition`。
