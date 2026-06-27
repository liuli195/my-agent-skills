---
comet_change: refactor-pr-flow-init
role: technical-design
canonical_spec: openspec
---

# PR Flow Init Refactor Design

## 背景

现有 `pr-flow-init`（拉取请求流程初始化）会直接写默认 `.pr-flow/config.yaml`（配置文件）、PR template（拉取请求模板）和 `.gitignore`（忽略文件）。这个入口能快速启用 PR Flow（拉取请求流程），但默认配置无法表达仓库真实的 GitHub（代码托管平台）远端规则、review gate（审查门禁）、hotfix（热修复）绕过权限和 cleanup（清理）策略依赖。

本次重构把初始化前置为 agent（代理）问答、配置草案、只读校验、建议输出和最终确认写入。script（脚本）只保留确定性的校验和本地写入能力，不承担交互和远端配置。

## 目标

- `pr-flow-init` Skill（初始化技能）负责 agent（代理）问答、草案展示、校验摘要和写入确认。
- PR Flow init（拉取请求流程初始化）的 Plugin（插件）/Skill（技能）内容按用户场景组织，并使用 progressive disclosure（渐进式披露）。
- questionnaire（问答模板）固定问题、固定选项、选择后果和跳转规则，避免 agent（代理）临场发挥。
- `pr_flow.py`（共享脚本）新增 `validate --config <path>`（校验命令），只读配置草案并输出问题和建议。
- `init`（初始化）脚本保留本地写入能力，但只写已确认配置。
- `setup.github`（GitHub 配置建议）只作为后续人工配置输入，不被运行命令消费。

## 非目标

- 不做 script（脚本）终端交互。
- 不自动配置 GitHub（代码托管平台）远端规则。
- 不试运行 diagnose、complete、cleanup、hotfix 或 tweak（诊断、收尾、清理、热修复、小改）。
- 不新增 GitHub workflow（GitHub 工作流）。
- 不改变 complete、cleanup、hotfix 和 tweak（收尾、清理、热修复、小改）的运行语义。

## 技术方案

### Skill（技能）结构

`plugins/pr-flow/skills/pr-flow-init/SKILL.md`（技能说明）只保留入口信息：

- Hard Boundaries（硬边界）。
- Closed Loop（闭环）。
- Required Flow（必需流程）。
- Output（输出）。
- `references/`（参考文件）清单。

细节放入固定参考文件：

```text
plugins/pr-flow/skills/pr-flow-init/
  SKILL.md
  references/
    questionnaire.md
    config-draft.md
    validation.md
```

Plugin（插件）/Skill（技能）整体内容和 `references/`（参考文件）按用户场景组织，而不是按 YAML（配置格式）字段或 script（脚本）函数组织。场景覆盖：

- 初次启用 PR Flow（拉取请求流程）。
- 选择 review gate（审查门禁）。
- 启用 hotfix（热修复）直推。
- 配置 cleanup（清理）行为。
- 处理 GitHub（代码托管平台）远端配置建议。
- 最终写入或覆盖本地配置。

Plugin（插件）级验收范围只覆盖会描述或路由 init（初始化）的可见入口：`.codex-plugin/plugin.json`、`.claude-plugin/plugin.json` 和 `skills/pr-flow/SKILL.md`（总入口）。complete、cleanup、hotfix 和 tweak（收尾、清理、热修复、小改）入口不做无关重排。

### 固定问答模板

`references/questionnaire.md`（问答模板）是 agent（代理）的固定执行模板，必须包含固定问题、固定选项、选择后果和跳转规则。agent（代理）不得新增临场问题、跳过最终确认，或把用户沉默当作确认。

问答结果生成两类内容：

- 运行配置：写入 `.pr-flow/config.yaml`（配置文件）并供 PR Flow（拉取请求流程）命令消费。
- `setup.github`（GitHub 配置建议）：记录远端配置意图，只用于后续人工配置和建议展示。

### 配置草案

`references/config-draft.md`（配置草案规则）定义草案结构、默认值、分支覆盖和 `setup.github`（GitHub 配置建议）字段。草案继续沿用现有 `defaults`（默认配置）加 `branches`（分支覆盖）模型。

`setup.github`（GitHub 配置建议）可记录：

- protected branches（受保护分支）。
- required checks（必需检查）。
- required review（必需审查）。
- allowed merge methods（允许合并方式）。
- auto-delete head branch（自动删除源分支）。
- Rulesets bypass（规则集绕过权限）。

complete、cleanup、hotfix、tweak 和 diagnose（收尾、清理、热修复、小改、诊断）不得消费 `setup.github`（GitHub 配置建议）。

### validate（校验）

新增 `pr_flow.py validate --config <path>`（校验命令）。它只读取指定 YAML（配置格式）文件，不写 `.pr-flow/config.yaml`（配置文件），不调用 GitHub API（GitHub 接口），不执行配置里的命令，也不运行 PR Flow（拉取请求流程）业务命令。

输出分三类：

- error（错误）：配置不可用或会让流程失败。
- warning（警告）：配置可写入，但存在明显流程风险。
- setup suggestion（配置建议）：需要用户或 agent（代理）另行处理的 GitHub（代码托管平台）或环境事项。

校验覆盖最小必要依赖：

- hotfix（热修复）：`allowHotfixPush: true`（允许热修复直推）需要授权短语、验证命令、remote（远端名），并提示 Rulesets bypass（规则集绕过权限）。
- review gate（审查门禁）：`github`（GitHub 审查）或 `dual`（双门禁）提示 required review（必需审查）；`local`（本地审查）或 `dual`（双门禁）要求 evidencePath（证据路径）并提示 review-pass.json（审查通过文件）契约。
- checks（检查）：wait（等待）只控制等待，不定义 required checks（必需检查）；required checks（必需检查）只能作为 GitHub Rulesets（GitHub 规则集）建议。
- merge strategy（合并方式）：本地配置必须提示对应 GitHub（代码托管平台）允许的 merge method（合并方式）。
- cleanup（清理）：auto-delete head branch（自动删除源分支）和 cleanup（清理）可能职责重叠，输出 warning（警告）。
- tweak（小改）：只跳过插件内 review gate（审查门禁），不能绕过远端 required review（必需审查）。

如果 validate（校验）输出 error（错误），`init`（初始化）必须停止且不得写入任何本地初始化文件。warning（警告）和 setup suggestion（配置建议）展示后可以继续等待用户最终确认。

### init（初始化）写入路径

`init`（初始化）脚本从“生成默认配置”改为“写入已确认配置”。写入路径使用确认配置输入，例如 `--config <path>`（配置文件路径）。

旧的无配置默认调用不得静默写默认文件；实现可以让旧调用失败并提示使用 `pr-flow-init` Skill（初始化技能），或仅保留参数解析但不写入。

写入范围保持最小：

- `.pr-flow/config.yaml`（配置文件）。
- `.pr-flow/pr-template.md`（拉取请求模板）。
- `.pr-flow/.gitignore`（忽略文件）。

它不写 GitHub（代码托管平台）远端，不提交、不推送、不合并。

## 测试策略

- Skill（技能）文本测试：确认入口只保留边界、流程、输出和 `references/`（参考文件）清单。
- reference（参考文件）测试：确认 `questionnaire.md`、`config-draft.md` 和 `validation.md`（问答模板、配置草案规则、校验规则）存在并被入口引用。
- 文档契约测试：确认 Plugin（插件）/Skill（技能）内容按用户场景组织；questionnaire（问答模板）包含固定问题、固定选项、选择后果和跳转规则。
- CLI（命令行接口）测试：覆盖 validate（校验）成功、error（错误）、warning（警告）和 setup suggestion（配置建议）。
- 依赖矩阵测试：覆盖 hotfix（热修复）、review gate（审查门禁）、checks（检查）、merge strategy（合并方式）、cleanup（清理）、tweak（小改）和 fast/full verify（快速/完整验证）边界。
- init（初始化）测试：覆盖已确认配置写入路径，并确认旧默认调用不会静默写默认文件。
- 端到端回归：从 `pr-flow-init` Skill（初始化技能）入口加载 references（参考文件），模拟固定问答和最终确认，生成草案，运行只读 validate（校验），通过确认配置输入写入本地文件，再做写入后结构检查；不得运行 diagnose、complete、cleanup、hotfix 或 tweak（诊断、收尾、清理、热修复、小改）。
- 运行 OpenSpec（开放规格）严格校验和 PR Flow（拉取请求流程）相关快速测试。

## 风险和缓解

- 风险：用户误以为 `setup.github`（GitHub 配置建议）会自动执行。
  缓解：Skill（技能）、validate（校验）输出和配置草案都明确“建议，不自动执行”。

- 风险：固定问答模板变长。
  缓解：Plugin（插件）/Skill（技能）整体内容按用户场景组织，入口保持短，细节按需加载。

- 风险：旧默认 init（初始化）路径被误用。
  缓解：无确认配置输入时不得静默写默认文件；测试覆盖拒绝路径和确认配置写入路径。

## Spec Patch

OpenSpec（开放规格）delta spec（规格增量）已回写以下内容：

- agent-driven init（代理驱动初始化）和本地写入确认。
- read-only validate（只读校验）。
- hotfix（热修复）、review gate（审查门禁）和 GitHub（代码托管平台）配置依赖。
- scenario-oriented progressive disclosure（面向用户场景的渐进式披露）要求。
