## Why

Build and Verify（构建与验证）目前只输出各检查项耗时，无法用一个仓库自定的完整验证总耗时预算提供统一性能警告，也没有稳定、机器可读的诊断报告。需要在不阻断验证、不绑定目标仓库测试框架的前提下，为通用插件补充最小性能可观测能力。

## What Changes

- 为 `verify`（验证）配置增加可选的 `fullBudgetSeconds`（完整验证预算秒数），只在 `verify --full`（完整验证）完成全部检查后判断是否超预算。
- 超预算只输出性能警告，不提前终止检查，也不改变原有验证退出状态。
- 为 `verify --full`（完整验证）增加 `--performance-report`（性能报告）参数，用于主动生成固定格式的 JSON（结构化数据）报告。
- 超预算时无论是否传入报告参数都自动生成报告；未超预算时只在显式传入报告参数时生成。
- 报告固定覆盖写入 `.build-and-verify/runs/performance-report.json`，包含生成时间、运行时版本、总耗时、预算、超限状态、验证状态和逐项耗时。
- 未触发报告的运行不创建、不覆盖也不删除固定报告；报告中的生成时间用于识别它对应的运行。
- 初始化向导、配置校验和 Skill（技能）文档同步支持新配置与命令语义。
- 使用通用进程内测试和最少的临时目标仓库 E2E（端到端测试）验证插件能力，不修改本仓库业务验证配置或 CI（持续集成）。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `test-framework-plugin`: 扩展实际发布名为 Build and Verify（构建与验证）的通用插件契约，增加完整验证总耗时警告、显式诊断参数和固定性能报告行为。

## Impact

- 影响 `plugins/build-and-verify/**` 下的命令入口、运行器、运行 Skill（技能）、初始化 Skill（技能）及参考文档。
- 影响 `test-framework-plugin`（测试框架插件）规格和 Build and Verify（构建与验证）插件测试。
- 不新增依赖，不修改目标仓库业务检查，不配置 CI（持续集成），不修改用户级或缓存中的插件副本。
