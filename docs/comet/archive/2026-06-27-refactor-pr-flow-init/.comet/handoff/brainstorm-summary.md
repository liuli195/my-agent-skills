# Brainstorm Summary

- Change: refactor-pr-flow-init
- Date: 2026-06-27

## 确认的技术方案

`pr-flow-init` Skill（初始化技能）采用 progressive disclosure（渐进式披露）结构：入口只保留 hard boundaries（硬边界）、closed loop（闭环）、required flow（必需流程）、output（输出）和 `references/`（参考文件）清单。

初始化问答不由 script（脚本）执行。agent（代理）必须按 `references/questionnaire.md`（问答模板）的固定问题、固定选项、选择后果和跳转规则推进。按用户场景组织的是 PR Flow init（拉取请求流程初始化）的 Plugin（插件）/Skill（技能）整体内容和 `references/`（参考文件）：基础 PR 流程、review gate（审查门禁）、hotfix（热修复）、cleanup（清理）、GitHub（代码托管平台）远端配置建议和最终写入确认。

配置草案由 `references/config-draft.md`（配置草案规则）定义，校验和写入前摘要由 `references/validation.md`（校验规则）定义。`pr_flow.py validate --config <path>`（校验命令）只读草案文件，输出 error（错误）、warning（警告）和 setup suggestion（配置建议）。error（错误）必须阻止 init（初始化）写入；warning（警告）和 setup suggestion（配置建议）展示后可继续等待用户确认。

`init`（初始化）脚本保留本地写入能力，但只写已确认的配置输入，不做终端交互、不配置 GitHub（代码托管平台）、不试运行流程。旧的无配置默认调用不得静默写默认文件。

## 关键取舍与风险

- 保留脚本写入能力，但写入必须来自已确认配置输入；旧默认写入路径改为拒绝或非写入提示。
- `setup.github`（GitHub 配置建议）进入配置草案，但现有运行命令不消费，避免把建议误当自动化远端配置。
- fixed questionnaire（固定问答模板）减少 agent（代理）自由发挥；通过 Plugin（插件）/Skill（技能）整体内容的用户场景分组降低理解成本。
- cleanup（清理）和 auto-delete head branch（自动删除源分支）存在职责重叠；本变更只输出 warning（警告），不改 cleanup（清理）运行语义。

## 测试策略

- Skill（技能）包测试：确认入口引用 `references/questionnaire.md`、`config-draft.md` 和 `validation.md`（问答模板、配置草案规则、校验规则）。
- 文档契约测试：确认 Plugin（插件）/Skill（技能）整体内容按用户场景组织，并确认 questionnaire（问答模板）包含固定问题、固定选项、选择后果和跳转规则。
- CLI（命令行接口）测试：覆盖 validate（校验）成功、错误、警告和建议输出。
- 依赖矩阵测试：覆盖 hotfix（热修复）、review gate（审查门禁）、checks（检查）、merge strategy（合并方式）、cleanup（清理）、tweak（小改）和 fast/full verify（快速/完整验证）边界。
- init（初始化）测试：覆盖确认配置输入写入路径，并确认旧默认调用不会静默写默认文件。
- 端到端回归：从 `pr-flow-init` Skill（初始化技能）入口加载 references（参考文件），模拟固定问答、草案、只读 validate（校验）、最终确认、确认配置写入和写入后结构检查。

## Spec Patch

已回写 OpenSpec delta spec（开放规格变更规格）：

- 修改 `Repository PR Flow configuration`（仓库 PR Flow 配置）需求，加入 agent-driven init（代理驱动初始化）和 `setup.github`（GitHub 配置建议）边界。
- 新增 `PR Flow init validates confirmed configuration`（初始化校验已确认配置）需求。
- 新增 `PR Flow init uses scenario-oriented progressive-disclosure guidance`（初始化使用面向用户场景的渐进式披露指导）需求。
