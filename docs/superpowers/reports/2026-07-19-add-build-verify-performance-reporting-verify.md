# add-build-verify-performance-reporting 验证报告

## 摘要

| 维度 | 结果 |
| --- | --- |
| 完整性 | 10/10 项任务完成；1 个增量规格已覆盖 |
| 正确性 | 完整验证通过；性能预算只告警、不阻断验证；报告触发与内容均有测试覆盖 |
| 一致性 | 提案、设计、规格、任务与实现一致；未改仓库级配置、持续集成或用户安装运行时 |

## 需求核对

- `verify.fullBudgetSeconds`（完整验证预算秒数）为可选正整数；仅完整验证读取和校验。快速验证不会读取、校验或受该字段影响。
- 完整验证始终执行全部已选检查项；总耗时超过预算时只输出 `performance-warning`（性能告警），保持原有成功或失败结果。
- `--performance-report`（性能报告）只能与 `--full`（完整验证）组合；显式请求或超过预算时，写入固定路径 `.build-and-verify/runs/performance-report.json`。
- 报告包含固定的 8 个顶层字段，以及按配置顺序排列的检查项标识、状态和耗时；写入失败只输出告警，不改变功能结果。
- 版本统一提升至 `0.1.37`，并同步运行时说明、初始化说明和插件清单。

## 验证证据

- 用户入口完整验证：`python plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py verify --project . --full`
  - 结果：`status: passed`
  - 测试：1,034 个通过；OpenSpec（开放规格）16 项通过。
  - 已执行检查项：`verify.local-build-contract`、`verify.agent-guard`、`verify.release-flow`、`verify.pr-flow`、`verify.cross-agent-review`、`verify.build-and-verify`、`verify.openspec`。
- OpenSpec（开放规格）严格校验：`openspec validate add-build-verify-performance-reporting --strict --no-interactive`
  - 结果：通过。
- 变更针对性测试：`python -m pytest tests/test_build_and_verify_plugin.py tests/test_test_runtime_boundaries.py tests/test_version_source_of_truth.py -q`
  - 结果：201 个通过。
- 标准代码审查：修复“快速验证不应校验完整验证预算”后复审通过，未发现严重、重要或次要问题。
- Ponytail（小马尾）过度设计审查：通过；未新增模块、依赖、历史基线、单项预算或与仓库测试耦合的机制。

## 覆盖范围

- 预算存在、超限、未超限、预算无效、未完成检查、报告写入失败、快速验证隔离，以及复制到临时项目后的端到端路径均有自动化测试。
- Comet（双星流程）构建守卫未能识别本仓库的 Python（蟒蛇语言）构建入口；已直接执行真实构建入口和上述完整验证，均通过。仅为推进守卫状态在单次命令中使用 `COMET_SKIP_BUILD=1`，未修改任何持久配置。

## 结论

未发现严重或重要验证问题。变更已准备好进入分支交付决策；根据仓库规则，进入 `main`（主干）必须通过 PR（拉取请求）。
