## Why

`build-and-verify` runtime（运行时）当前只存在于用户级 Plugin（插件）安装缓存时，仓库文档和 CI（持续集成）无法依赖稳定入口。Plugin（插件）更新后用户级路径还会变化，导致验证命令入口难以配置和长期维护。

## What Changes

- `init`（初始化）写入 `.build-and-verify/config.json` 等配置时，同步复制当前 runtime（运行时）快照到仓库内固定目录。
- 新增显式 `update-runtime`（更新运行时）命令，用同一套 runtime（运行时）代码刷新仓库内快照。
- `build`（构建）和 `verify`（验证）运行前只做版本落后提示，不自动修改仓库文件。
- 仓库内 runtime（运行时）和用户级 runtime（运行时）保持同一份能力，不引入双入口差异。
- 更新 Skill（技能）文案、spec（规格）、测试和 CI（持续集成）入口，使用仓库内固定 runtime（运行时）路径。

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `test-framework-plugin`: 修改 `build-and-verify` Plugin（插件）初始化、运行入口和 runtime（运行时）同步要求。

## Impact

- 影响 `plugins/build-and-verify` 的 runtime（运行时）入口脚本和相关测试。
- 影响 `build-and-verify` Skill（技能）文案。
- 影响 `openspec/specs/test-framework-plugin` 的验收要求。
- 影响调用验证命令的仓库配置或 CI（持续集成）文档入口。
