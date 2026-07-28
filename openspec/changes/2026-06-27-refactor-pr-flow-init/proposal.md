## Why

当前 PR Flow（拉取请求流程）`init`（初始化）只写一份默认配置，无法表达不同仓库的 GitHub（代码托管平台）规则、hotfix（热修复）权限、review gate（审查门禁）和 cleanup（清理）策略依赖。结果是配置看似可用，但真正进入 complete（收尾）或 hotfix（热修复）时才暴露缺少远端规则、权限或证据的问题。

本变更让初始化从“写默认文件”升级为“agent（代理）问答、草案确认、配置校验、建议输出、确认后写入”，同时保留已有脚本写本地文件的能力。

## What Changes

- 更新 `pr-flow-init` Skill（技能）：由 agent（代理）逐项问答，形成 `.pr-flow/config.yaml`（配置文件）草案，展示校验结果和 GitHub（代码托管平台）配置建议。
- 将 PR Flow init（拉取请求流程初始化）的 Plugin（插件）和 Skill（技能）内容改为按用户场景组织，并使用渐进式披露结构。
- 入口文案只说明边界和必需流程；用户场景说明、固定问答、配置草案和校验规则放入 `references/`（参考文件）。
- 固定问答模板必须包含固定问题、固定选项、选择后果和跳转规则，避免 agent（代理）自由发挥。
- 保留 `init`（初始化）脚本写本地文件能力，但脚本只写入已确认配置，不做终端交互，也不自动配置远端。
- 新增或调整 `validate`（校验）入口：只读取 `--config <path>`（配置文件路径）并输出 error（错误）、warning（警告）和 setup suggestion（配置建议）。
- 增加跨配置依赖校验：hotfix（热修复）、review gate（审查门禁）、checks（检查）、merge strategy（合并方式）、cleanup（清理）、tweak（小改）与 GitHub（代码托管平台）配置意图的关系。
- 在配置中保留 `setup.github`（GitHub 配置建议）区，供 agent（代理）后续人工配置使用；现有运行命令不消费该区。
- 更新测试，覆盖 Skill（技能）边界、校验脚本、保留写入能力和依赖矩阵。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `pr-flow-plugin`: 修改 repository init（仓库初始化）契约、配置校验契约和 GitHub（代码托管平台）配置建议边界。

## Impact

- 影响 `plugins/pr-flow/skills/pr-flow-init/SKILL.md`（初始化技能说明）。
- 新增 `plugins/pr-flow/skills/pr-flow-init/references/`（参考文件）下的问答模板、配置草案规则和校验规则。
- 影响 `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`（共享脚本）。
- 影响 `tests/test_pr_flow_cli.py` 和插件包相关测试。
- 影响 `openspec/specs/pr-flow-plugin/spec.md`（PR Flow 插件规格）。
- 不新增依赖，不自动写 GitHub Rulesets（GitHub 规则集），不新增 GitHub workflow（GitHub 工作流）。
