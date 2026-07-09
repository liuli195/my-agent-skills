## Why

`build-and-verify-init`（构建与验证初始化）写入 `.build-and-verify/config.json`（配置文件）时，没有稳定保证同目录 `.gitignore`（忽略规则）包含所有本地运行目录。

这会让 cache（缓存）、runs（运行记录）或 backups（备份）目录在目标仓库里变成未忽略文件。

## What Changes

- 让 `.build-and-verify/.gitignore`（忽略规则）默认包含 `/cache/`、`/runs/` 和 `/backups/`。
- 让 `build-and-verify-init`（构建与验证初始化）参考规则要求始终补齐这三条规则。
- 更新测试，覆盖命令行 init（初始化）和向导写入模拟。

## Capabilities

### New Capabilities

- 无。

### Modified Capabilities

- `test-framework-plugin`: 初始化产物的 `.build-and-verify/.gitignore`（忽略规则）默认内容变更。

## Impact

- 影响 `plugins/build-and-verify`（构建与验证插件）的模板和 init（初始化）参考规则。
- 不新增依赖，不改变 runner（运行器）执行语义。
