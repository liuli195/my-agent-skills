## Context

PR Flow（拉取请求流程）现有 `init`（初始化）脚本会直接写默认 `.pr-flow/config.yaml`（配置文件）、PR template（拉取请求模板）和 `.gitignore`（忽略文件）。这个路径简单，但默认配置无法表达仓库实际的 GitHub Rulesets（GitHub 规则集）、required checks（必需检查）、required review（必需审查）、hotfix（热修复）绕过权限和 cleanup（清理）策略。

已有 PR Flow（拉取请求流程）设计明确不自动写 GitHub Rulesets（GitHub 规则集），也不提供 dry-run（试运行）。本次保持这个边界，只把初始化前的确认和校验补齐。

## Goals / Non-Goals

**Goals:**

- `pr-flow-init` Skill（初始化技能）负责 agent（代理）问答和确认流程。
- PR Flow init（拉取请求流程初始化）的 Plugin（插件）和 Skill（技能）内容采用 progressive disclosure（渐进式披露）和用户场景组织。
- 问答流程使用固定 questionnaire（问答模板），不允许 agent（代理）自由编造问题。
- `pr_flow.py`（共享脚本）提供 `validate`（校验）入口，只校验配置草案。
- `init`（初始化）脚本保留写入本地文件能力，但只写已确认的配置输入。
- 校验覆盖字段合法性和跨配置依赖。
- GitHub（代码托管平台）配置意图进入 `setup.github`（GitHub 配置建议）区，供 agent（代理）后续人工配置。
- `cross-agent-review`（跨代理审查）输出轻量 Markdown（标记文本）审查报告，主 agent（主代理）负责按 severity（严重级别）判断是否写入 pass marker（通过标记）。
- Agent Guard（代理守卫）使用统一 `.local/guard/evidence/` 默认目录读取主 agent（主代理）生成的 guard-defined evidence（守卫定义证据）。

**Non-Goals:**

- 不做 script（脚本）终端交互。
- 不自动配置 GitHub（代码托管平台）远端规则。
- 不试运行 diagnose、complete、cleanup、hotfix、tweak（诊断、收尾、清理、热修复、小改）。
- 不新增 GitHub workflow（GitHub 工作流）。
- 不改变 complete、cleanup、hotfix、tweak（收尾、清理、热修复、小改）的运行语义。

## Decisions

### 1. Skill（技能）负责问答，script（脚本）保持确定性

`pr-flow-init` Skill（初始化技能）说明 agent（代理）必须先问答、生成草案、调用 validate（校验）、展示草案和建议，再等待用户确认。script（脚本）不使用 `input()`（终端输入）或 prompt（提示）做交互。

保留脚本写入能力是为了兼容已有入口和测试，也让 agent（代理）确认后可以调用同一确定性写入路径。

### 2. Plugin（插件）和 Skill（技能）内容使用渐进式披露和用户场景组织

参考 build-and-verify-init（构建与验证初始化）的结构，`pr-flow-init` Skill（初始化技能）入口只保留：

- Hard Boundaries（硬边界）。
- Closed Loop（闭环）说明。
- Required Flow（必需流程）。
- Output（输出）摘要。
- `references/`（参考文件）清单。

Plugin（插件）和 Skill（技能）的内容结构必须按用户场景展开，而不是按 YAML（配置格式）字段或脚本函数平铺。入口只给用户当前需要的最小信息；深入细节通过 `references/`（参考文件）渐进加载。

用户场景层级：

- 初次启用 PR Flow（拉取请求流程）。
- 选择 review gate（审查门禁）。
- 启用 hotfix（热修复）直推。
- 配置 cleanup（清理）行为。
- 处理 GitHub（代码托管平台）远端规则建议。
- 覆盖或写入本地配置。

Plugin（插件）级验收范围限定为会描述或路由 init（初始化）的可见入口：`.codex-plugin/plugin.json`、`.claude-plugin/plugin.json` 和 `skills/pr-flow/SKILL.md`（总入口）。complete、cleanup、hotfix 和 tweak（收尾、清理、热修复、小改）入口不因为本变更做无关重排。

细节拆到固定参考文件，每个参考文件也必须沿用上述用户场景组织：

- `references/questionnaire.md`（问答模板）：固定问题、固定选项、选择后果和跳转规则。
- `references/config-draft.md`（配置草案规则）：`.pr-flow/config.yaml`（配置文件）草案结构、默认值和 `setup.github`（GitHub 配置建议）结构。
- `references/validation.md`（校验规则）：validate（校验）输出、依赖矩阵、写入前摘要和写入后结构校验。

agent（代理）必须按 questionnaire（问答模板）推进，不得临场新增问题、跳过最终确认或把用户沉默视为确认。

### 3. validate（校验）只读草案文件

新增 `pr_flow.py validate --config <path>`（校验命令）。它只读取 YAML（配置格式）文件，输出结构化结果，不写文件，不执行配置里的命令，不调用 GitHub API（GitHub 接口）。

输出分三类：

- error（错误）：配置不可写入或会让 PR Flow（拉取请求流程）运行路径失败。
- warning（警告）：配置可写入，但有明显流程风险。
- setup suggestion（配置建议）：需要用户或 agent（代理）在 GitHub（代码托管平台）或本地环境中另行处理的事项。

### 4. init（初始化）写入已确认配置

`init`（初始化）脚本从“生成默认配置”调整为“写入已确认配置”。写入路径使用确认配置输入，例如 `--config <path>`（配置文件路径）。

任何本地写入都必须来自已确认配置输入。旧的无配置默认调用不得静默写默认文件；实现可以让旧调用失败并提示使用 `pr-flow-init` Skill（初始化技能），或仅保留参数解析但不写入。

写入边界：

- 写 `.pr-flow/config.yaml`（配置文件）。
- 写 `.pr-flow/pr-template.md`（拉取请求模板）。
- 写 `.pr-flow/.gitignore`（忽略文件）。
- 不写 GitHub（代码托管平台）远端。
- 不创建提交、不推送、不合并。

写入前必须复用 validate（校验）。如果 validate（校验）输出 error（错误），`init`（初始化）必须停止且不得写入；warning（警告）和 setup suggestion（配置建议）展示后可以继续等待用户确认。

### 5. setup.github（GitHub 配置建议）是建议，不是运行配置

`setup.github`（GitHub 配置建议）记录远端配置意图，例如 protected branches（受保护分支）、required checks（必需检查）、required review（必需审查）、allowed merge methods（允许合并方式）、auto-delete head branch（自动删除源分支）和 Rulesets bypass（规则集绕过权限）。

现有运行命令不消费 `setup.github`（GitHub 配置建议）。它只给 agent（代理）后续人工配置和校验提示使用。

### 6. 校验依赖矩阵

validate（校验）必须覆盖这些依赖：

- hotfix（热修复）：`allowHotfixPush: true`（允许热修复直推）需要 authorization phrase（授权短语）、hotfix verify command（热修复验证命令）、remote（远端名），并提示 Rulesets bypass（规则集绕过权限）。
- review gate（审查门禁）：`github`（GitHub 审查）或 `dual`（双门禁）提示 required review（必需审查）；`local`（本地审查）或 `dual`（双门禁）要求 evidencePath（证据路径）和 review-pass.json（审查通过文件）字段契约。
- checks（检查）：wait（等待设置）只控制等待，不定义 required checks（必需检查）；required checks（必需检查）只能作为 GitHub Rulesets（GitHub 规则集）建议。
- merge strategy（合并方式）：配置的 merge/squash/rebase（合并、压缩合并、变基合并）必须和 GitHub（代码托管平台）允许方式一致。
- cleanup（清理）：auto-delete head branch（自动删除源分支）可能和 cleanup（清理）删除远端源分支职责重叠，默认给 warning（警告）。
- tweak（小改）：只跳过插件内 review gate（审查门禁），不能绕过远端 required review（必需审查）。

### 7. Cross-agent review（跨代理审查）职责分离

`cross-agent-review run`（跨代理审查运行）只负责派发 reviewer（审查代理）并聚合 Markdown（标记文本）报告。reviewer（审查代理）输出必须包含 `Severity: CRITICAL|IMPORTANT|WARNING|SUGGESTION`（严重级别）。脚本不解析 finding（发现项）、不去重、不计算阻断数量，也不生成旧 `.local/cross-agent-review/.../review-pass.json`（审查通过文件）。

主 agent（主代理）读取 `review-report.md`（审查报告）后做语义判断。只有没有未处理 CRITICAL（严重阻断）或 IMPORTANT（重要阻断）时，主 agent（主代理）才调用 `mark-pass`（标记通过）写入 `.local/guard/evidence/<profile_id>/cross_agent_review_pass/<change>/<head_ref_short>/pass.json`。

Agent Guard（代理守卫）只通过 artifacts.yaml（产物注册文件）读取该 guard-defined evidence（守卫定义证据），不得准备 cross-agent-review（跨代理审查）输入、派发 reviewer（审查代理）或推进 Comet phase（彗星阶段）。

插件内部保留 reviewer（审查代理）480 秒和 SDK dispatch（开发包派发）540 秒 timeout（超时）。主 agent（主代理）不得在插件命令外层再包装短于 540 秒的 timeout/watchdog（超时/看门等待）。

## Risks / Trade-offs

- 配置问答变长 -> 通过 Skill（技能）分组提问和默认值降低负担。
- `setup.github`（GitHub 配置建议）可能被误认为脚本会执行 -> Skill（技能）和 validate（校验）输出必须明确“建议，不自动执行”。
- 保留 `init`（初始化）写入能力可能让旧默认路径继续存在 -> 测试必须覆盖无配置调用不得静默写默认文件，确认配置输入才允许写入。
- auto-delete head branch（自动删除源分支）与 cleanup（清理）存在职责重叠 -> 本次只提示风险，不改 cleanup（清理）运行语义。

## Migration Plan

1. 更新 delta spec（规格变更），明确 init（初始化）、validate（校验）和 setup.github（GitHub 配置建议）契约。
2. 更新 `pr-flow-init` Skill（初始化技能）文档，并新增 `references/`（参考文件）模板。
3. 增加 validate（校验）入口和结构化输出。
4. 调整 init（初始化）写入路径，只支持已确认配置输入写入。
5. 更新测试，覆盖旧默认写入被拒绝、确认配置写入、端到端初始化回归和依赖矩阵。
6. 更新 cross-agent-review（跨代理审查）、Agent Guard（代理守卫）和 Comet review gate（彗星审查门禁）规格，记录 pass marker（通过标记）职责和默认 evidence（证据）路径。
