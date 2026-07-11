## Why

仓库要求规划产物使用简体中文，但 `.comet/config.yaml` 没有声明语言，导致新 Comet（双星流程）变更默认使用英文，并在 open（开启）阶段触发语言守卫冲突。

根因是项目级 Comet（双星流程）配置缺少受当前运行时支持的 `language: zh-CN`。

## What Changes

- 在 `.comet/config.yaml` 显式设置 `language: zh-CN`。
- 保持上下文压缩和自动阶段衔接配置不变。
- 验证配置可解析，且新变更会继承中文产物语言。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

无；本次只修正仓库级工作流配置，不改变产品规格。

## Impact

- 之后新建的 Comet（双星流程）变更默认生成中文规划产物。
- 已存在变更仍使用各自 `.comet.yaml` 保存的语言，不受影响。
