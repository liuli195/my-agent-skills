## Implementation

在 Global Command Guard（全局命令守卫）配置中增加 `skip_when`（跳过条件）列表。每个条件读取一个声明式 YAML（配置文件）：

- `path`: 相对路径模板，支持 `{change}` 等现有上下文值。
- `field`: 要读取的 YAML（配置文件）字段。
- `in`: 允许跳过的字段值列表。

Runtime（运行时）在命令匹配后、读取 evidence（证据）前评估 `skip_when`（跳过条件）。任一条件命中时，该 guard（守卫）不加入匹配集合，也不检查 evidence（证据）。

`comet-review-gate`（Comet 审查门禁）模板声明：

```yaml
skip_when:
  - yaml:
      path: openspec/changes/{change}/.comet.yaml
      field: workflow
      in:
        - hotfix
        - tweak
```

这样 Runtime（运行时）保持通用：它只读取配置声明的 YAML（配置文件）字段，不内置 Comet（彗星流程）业务判断。

## Verification

- 新增测试覆盖 full（完整）流程仍然阻断。
- 新增测试覆盖 hotfix（热修复）和 tweak（小改）流程放行。
- 新增校验器测试覆盖 `skip_when`（跳过条件）有效配置。
- 运行 Agent Guard（代理守卫）相关 pytest（测试）和 OpenSpec（开放规格）校验。
