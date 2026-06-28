---
comet_change: optimize-pr-flow-init-template
role: technical-design
canonical_spec: openspec
---

# PR Flow Init Template Design

## 背景

`pr-flow-init`（拉取请求流程初始化）已经有入口 Skill（技能）和三个 reference（参考文件），但现有问答模板仍把本地运行配置、GitHub（代码托管平台）远端配置建议和用户操作待办混在一起。实际交互中，default PR target branch（默认拉取请求目标分支）、branch protection（分支保护）、PR review（拉取请求代码审查）和 PR status checks（拉取请求状态检查）容易被混问。

本次变更只修正模板和测试契约，不改 `pr_flow.py`（拉取请求流程脚本）运行语义。

## 目标

- `questionnaire.md`（问答模板）使用本轮最新模拟流程。
- `config-draft.md`（配置草案规则）先展示用户可读摘要，再展示 YAML（配置格式）细节。
- `validation.md`（校验规则）按 error（错误）、warning（警告）、remote tasks（远端待办）分组。
- GitHub（代码托管平台）远端待办使用官方规则名，且明确只是建议，不代表已应用。
- 保留“已有配置、分支状态或历史记录不能代替用户回答或确认”的入口约束。

## 非目标

- 不自动创建或修改 GitHub Rulesets（GitHub 规则集）。
- 不新增可执行初始化向导。
- 不扩展 `setup.github`（GitHub 配置建议）运行时数据模型。
- 不改变 complete、cleanup、hotfix、tweak（收尾、清理、热修复、小改）运行语义。

## 技术方案

采用最小模板修正。

`references/questionnaire.md`（问答模板）改成固定流程：

1. 自动检查仓库和 GitHub（代码托管平台）当前状态，包括默认分支、远端分支、Rulesets（规则集）、branch protection（分支保护）、merge methods（合并方式）、auto-delete head branch（自动删除源分支）和可用 PR status checks（拉取请求状态检查）。
   - 若 GitHub access（GitHub 访问权限）、`gh` CLI（GitHub 命令行工具）或 network（网络）不可用，必须显示 `not inspected`（未检查）或 `no access`（无权限），只输出推荐远端待办，不声明远端当前状态已确认。
2. 询问 default PR target branch（默认拉取请求目标分支）。
3. 询问哪些分支需要通过 GitHub Rulesets（GitHub 规则集）保护；远端待办必须写成创建或更新 branch ruleset（分支规则集），启用 `Require a pull request before merging`（合并前要求拉取请求），默认 `required_approving_review_count: 0`。
4. 询问 PR status checks（拉取请求状态检查）；没有具体 check name（检查名称）时，不编造名称，只记录新增或识别检查后再启用 `Require status checks to pass before merging`（合并前要求状态检查通过）。
5. 询问是否启用 CodeQL security check（CodeQL 安全检查）；只提供“开启”和“不开启”。开启时，远端待办必须要求在 GitHub Rulesets（GitHub 规则集）中配置 `Require code scanning results`（要求代码扫描结果）、选择 `CodeQL` 作为 code scanning tool（代码扫描工具），并采用 GitHub 默认阈值。
6. 询问 hotfix（热修复）直推；只有允许后才问授权短语是复用现有还是新设。
7. 询问 allowed merge methods（允许合并方式）。
8. 展示 GitHub 推荐配置（GitHub 远端配置建议）场景，列出 remote tasks（远端待办）并说明没有写入远端。
9. 最终写入确认必须在只读 validate（校验）摘要之后，用户沉默不能视为确认。

`references/config-draft.md`（配置草案规则）拆成四块展示：

- 本地将写入：`.pr-flow/config.yaml`（配置文件）、PR template（拉取请求模板）、`.gitignore`（忽略文件）。
- GitHub 当前状态：只展示已检查到的远端状态。
- GitHub 推荐配置：只作为人工或后续 agent（代理）待办。
- YAML（配置格式）附录：只在用户可读摘要之后出现。

`references/validation.md`（校验规则）继续描述本地 validate（校验）语义，但输出组织改为：

- error（错误）：阻止写入。
- warning（警告）：允许继续但需要用户看见风险。
- remote tasks（远端待办）：用可执行步骤说明 GitHub（代码托管平台）配置。

## 测试策略

先改 `tests/test_pr_flow_cli.py`（测试文件）添加失败测试，锁定：

- read-only inspection（只读检查）必须出现在问答前。
- 最新六个主问题必须存在，旧的独立 review gate（审查门禁）不能再作为主问题。
- GitHub（代码托管平台）远端待办必须包含官方规则名。
- CodeQL security check（CodeQL 安全检查）必须在 PR status checks（拉取请求状态检查）之后、hotfix（热修复）之前，并锁定 `Require code scanning results`（要求代码扫描结果）、`CodeQL` 和 GitHub 默认阈值。
- GitHub 推荐配置（GitHub 远端配置建议）必须作为 final confirmation（最终确认）前的显式场景出现。
- 草案和校验说明必须先给用户可读摘要，再给 YAML（配置格式）细节。
- 既有用户场景测试必须替换旧 `review gate`（审查门禁）、`cleanup`（清理）和 `GitHub setup suggestions`（GitHub 配置建议）主流程断言。
- 既有 plugin entrypoint（插件入口）路由测试继续保留；只有入口文案与 init（初始化）新契约冲突时才修改入口文件。

测试失败后，再更新三个 reference（参考文件）到最小可读模板。最后运行 focused PR Flow（拉取请求流程）测试和 OpenSpec strict validation（开放规格严格校验）。

## 风险和缓解

- 风险：模板变长。缓解：入口 Skill（技能）保持短，细节继续放到 reference（参考文件）。
- 风险：用户误以为 GitHub（代码托管平台）远端已配置。缓解：摘要明确区分当前状态、推荐配置和本地写入。
- 风险：测试只检查文字。缓解：测试锁定流程顺序、官方规则名和输出结构，不为文档引入额外执行引擎。

## Spec Patch

本变更已有 OpenSpec delta（开放规格增量）：新增 GitHub（代码托管平台）可执行远端待办要求，并修改 PR Flow init（拉取请求流程初始化）的渐进式模板契约。实现阶段不需要额外回写新的 Spec Patch（规格补丁），除非发现验收场景仍缺失。
